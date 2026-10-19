# CortesByLRM

Pipeline local e auditável para criar cortes verticais **sem precisar aparecer**, com materiais autorizados e controle financeiro de campanhas. Repositório público: **não envie mídias de clientes, contratos, tokens ou credenciais**.

## P0 — o que já está implementado nesta branch

- Importação de transcrição SRT, sugestão heurística de cortes entre 15 e 60 segundos.
- Manifesto JSON registrando base de direitos, evidência declarada e revisão obrigatória.
- Exportação local de vídeos 9:16 via FFmpeg (sem crop agressivo), com legendas **SRT separadas**.
- Registro de visualizações totais/elegíveis e valor em R$ com status estimado/aprovado/recebido.
- Testes unitários sem dependências externas e CI GitHub Actions.

**O programa não baixa vídeos, não valida juridicamente a prova, não publica automaticamente e não garante viralização.** Revisão editorial/autoral antes de qualquer postagem é obrigatória.

## Executar (Python 3.10+)

```bash
git clone https://github.com/lrm-lgtm/CortesByLRM.git
cd CortesByLRM
git switch feat/p0-pipeline-cortes-2026-10
python -m venv .venv
# Ative o ambiente virtual (Windows: .venv\\Scripts\\activate)
python -m pip install -e .
python -m unittest discover -s tests -v
```

É necessário instalar `ffmpeg` e disponibilizá-lo no PATH **apenas para renderizar MP4**. Para sugerir trechos e registrar receitas, Python basta.

### 1. Planejar cortes de material local autorizado

```bash
cortesbylrm plan --video media/original.mp4 --srt media/original.srt \
  --basis campanha --proof "https://endereco-do-regulamento-ou-autorizacao" \
  --campaign "Nome da campanha" --output data/plano.json
```

A base `proprio` serve para vídeos realmente seus; `licenciado` pressupõe autorização verificável; `campanha` requer conferir regras de uso, prazo e plataforma. O campo `--proof` é uma referência informada pelo operador, **não uma validação automática**.

### 2. Conferir plano e gerar um corte

```bash
cortesbylrm render --manifest data/plano.json --clip 1 --dry-run
cortesbylrm render --manifest data/plano.json --clip 1 --outdir out
```

Gera `out/corte_01.mp4` e `out/corte_01.srt`. As legendas ainda não aparecem embutidas no MP4; abra o SRT no seu editor antes de publicar. A transcrição deve ter duração suficiente para obter sugestões. Use `examples/demo.srt` com um **vídeo próprio** de teste para conhecer o fluxo.

### 3. Registrar o resultado financeiro

```bash
cortesbylrm record --platform youtube --url https://example.org/clip \
  --views 10000 --eligible-views 2000 --status estimated --amount 4.00 \
  --campaign "Campanha teste"
cortesbylrm report
```

`estimated` = estimativa, `approved` = valor aprovado na campanha e `paid` = valor realmente recebido. **Não registre o mesmo pagamento duas vezes como receitas distintas**: a migração de status por ID será feita na P1.

Ver planejamento e limites detalhados em [docs/P0.md](docs/P0.md).
