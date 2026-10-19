"""CLI de P0: planejar, renderizar e registrar monetização. Sem publicar automaticamente."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from .core import check_rights, clip_srt, ffmpeg_command, parse_srt, serialize_suggestions, suggest_cuts


def json_write(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def json_read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def plan(args) -> None:
    check_rights(args.basis, args.proof)
    video, subtitle = Path(args.video).expanduser().resolve(), Path(args.srt).expanduser().resolve()
    if not video.is_file():
        raise ValueError("Vídeo local não encontrado.")
    if not subtitle.is_file():
        raise ValueError("SRT não encontrado.")
    cues = parse_srt(subtitle.read_text(encoding="utf-8-sig"))
    if not cues:
        raise ValueError("Nenhuma legenda SRT válida encontrada.")
    clips = serialize_suggestions(suggest_cuts(cues, limit=args.limit))
    data = {
        "schema_version": 1,
        "source_video": str(video),
        "source_srt": str(subtitle),
        "rights": {"basis": args.basis, "evidence": args.proof},
        "campaign": args.campaign,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "clips": clips,
        "review_required": True,
        "publish_automatically": False,
    }
    json_write(Path(args.output), data)
    print(f"Plano salvo: {args.output} | sugestões: {len(clips)}")
    if not clips:
        print("Sem sugestões: forneça uma transcrição mais longa.")


def render(args) -> None:
    manifest = json_read(Path(args.manifest))
    rights = manifest.get("rights", {})
    check_rights(rights.get("basis", ""), rights.get("evidence", ""))
    clips = manifest.get("clips", [])
    if args.clip < 1 or args.clip > len(clips):
        raise ValueError("Número de corte não existe no manifesto.")
    clip = clips[args.clip - 1]
    video, srt = Path(manifest["source_video"]), Path(manifest["source_srt"])
    if not video.is_file() or not srt.is_file():
        raise ValueError("Arquivo fonte ausente; confira caminhos locais no manifesto.")
    target = Path(args.outdir)
    output = target / f"corte_{args.clip:02}.mp4"
    caption = target / f"corte_{args.clip:02}.srt"
    command = ffmpeg_command(video, output, clip["start"], clip["end"])
    if args.dry_run:
        print(json.dumps({"command": command, "srt": str(caption)}, ensure_ascii=False, indent=2))
        return
    if not shutil.which("ffmpeg"):
        raise ValueError("FFmpeg não encontrado no PATH; use --dry-run ou instale o FFmpeg.")
    target.mkdir(parents=True, exist_ok=True)
    original = parse_srt(srt.read_text(encoding="utf-8-sig"))
    caption.write_text(clip_srt(original, clip["start"], clip["end"]), encoding="utf-8")
    subprocess.run(command, check=True)
    print(f"Gerados: {output} e {caption}")
    print("Atenção: SRT separado, sem legenda queimada. Revisar antes de publicar.")


def record(args) -> None:
    if args.views < 0 or args.eligible_views < 0 or args.eligible_views > args.views:
        raise ValueError("Visualizações devem ser consistentes e não negativas.")
    if args.amount < 0:
        raise ValueError("Valor monetário deve ser não negativo.")
    if not args.url.startswith(("https://", "http://")):
        raise ValueError("Forneça URL completa da publicação.")
    path = Path(args.ledger)
    data = json_read(path) if path.exists() else []
    if not isinstance(data, list):
        raise ValueError("Formato de controle financeiro inválido.")
    data.append({
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "campaign": args.campaign,
        "platform": args.platform,
        "url": args.url,
        "views_total": args.views,
        "views_eligible": args.eligible_views,
        "status": args.status,
        "amount_brl": round(args.amount, 2),
    })
    json_write(path, data)
    print(f"Registrado ({args.status}) em {path}")


def report(args) -> None:
    path = Path(args.ledger)
    data = json_read(path) if path.exists() else []
    print("Relatório experimental | registros:", len(data))
    for status in ("estimated", "approved", "paid"):
        rows = [x for x in data if x.get("status") == status]
        total = sum(float(x.get("amount_brl", 0)) for x in rows)
        print(f"{status}: R$ {total:.2f} ({len(rows)} registros)")
    print("Atenção: registros separados não comprovam pagamento sem evidência externa.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cortesbylrm", description="CortesByLRM P0")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="Seleciona sugestões de cortes a partir de SRT")
    p.add_argument("--video", required=True)
    p.add_argument("--srt", required=True)
    p.add_argument("--basis", choices=["proprio", "licenciado", "campanha"], required=True)
    p.add_argument("--proof", required=True, help="Referência local/URL da comprovação dos direitos")
    p.add_argument("--campaign", default="")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--output", default="data/plano.json")
    p.set_defaults(func=plan)

    p = sub.add_parser("render", help="Exporta MP4 9:16 + SRT para revisão humana")
    p.add_argument("--manifest", default="data/plano.json")
    p.add_argument("--clip", type=int, default=1)
    p.add_argument("--outdir", default="out")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=render)

    p = sub.add_parser("record", help="Registra receita estimada/aprovada/recebida")
    p.add_argument("--ledger", default="data/financeiro.json")
    p.add_argument("--campaign", default="")
    p.add_argument("--platform", choices=["youtube", "instagram", "tiktok", "facebook", "other"], required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--views", type=int, default=0)
    p.add_argument("--eligible-views", type=int, default=0)
    p.add_argument("--status", choices=["estimated", "approved", "paid"], required=True)
    p.add_argument("--amount", type=float, required=True, help="Valor em R$")
    p.set_defaults(func=record)

    p = sub.add_parser("report", help="Resume registros financeiros por status")
    p.add_argument("--ledger", default="data/financeiro.json")
    p.set_defaults(func=report)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"Erro: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
