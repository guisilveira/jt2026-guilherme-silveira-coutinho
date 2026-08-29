import glob
import json
import os

THREADS = [
    {
        "id": "01a0486c-7f91-7a93-9a56-3701bd0d2fef",
        "filename": "01_execucao_e_analise.md",
        "title": "Execução e análise",
        "description": "inspeção dos dados, implementação dos ciclos, geração dos artefatos e validações.",
    },
    {
        "id": "01a0435a-9bec-77a2-9cd3-4b4302b2dd2e",
        "filename": "02_planejamento_e_revisao.md",
        "title": "Planejamento e revisão",
        "description": "definição dos critérios, revisão crítica dos planos e resultados, identificação de inconsistências e preparação das instruções enviadas ao agente executor.",
    },
]

output_dir = os.path.dirname(os.path.abspath(__file__))

for item in THREADS:
    # Localiza todas as partes/arquivos da thread em ordem cronológica
    matches = sorted(
        glob.glob(
            os.path.expanduser(f"~/.codex/sessions/**/rollout-*{item['id']}*.jsonl"),
            recursive=True,
        )
    )

    if not matches:
        print(f"❌ Nenhum arquivo encontrado para a thread {item['id']}")
        continue

    out_path = os.path.join(output_dir, item["filename"])
    seen_ids = set()
    turns_count = 0

    with open(out_path, "w", encoding="utf-8") as f_out:
        f_out.write(f"# {item['title']}\n\n")
        f_out.write(f"> **Escopo:** {item['description']}\n\n")
        f_out.write(f"> **Thread ID:** `{item['id']}`  \n")
        f_out.write("---\n\n")

        # Itera por todas as partes da sessão (do primeiro ao último dia)
        for rollout_path in matches:
            with open(rollout_path, "r", encoding="utf-8") as f_in:
                for line in f_in:
                    try:
                        data = json.loads(line)
                        if data.get("type") == "event_msg":
                            payload = data.get("payload", {})
                            if payload.get("type") == "item_completed":
                                sub_item = payload.get("item", {})
                                item_type = sub_item.get("type")

                                if item_type in ["UserMessage", "AgentMessage"]:
                                    # Evita duplicações caso um item apareça em mais de um arquivo de checkpoint
                                    msg_id = sub_item.get("id")
                                    if msg_id:
                                        if msg_id in seen_ids:
                                            continue
                                        seen_ids.add(msg_id)

                                    role = (
                                        "👤 Usuário"
                                        if item_type == "UserMessage"
                                        else "🤖 Codex"
                                    )
                                    content = sub_item.get("content", [])
                                    texts = [
                                        b.get("text", "")
                                        if isinstance(b, dict)
                                        else str(b)
                                        for b in content
                                    ]
                                    msg = "\n".join(texts).strip()

                                    if msg:
                                        f_out.write(f"## {role}\n\n{msg}\n\n---\n\n")
                                        turns_count += 1
                    except Exception:
                        continue

    print(
        f"✅ Exportado: {item['filename']} ({turns_count} turnos em {len(matches)} arquivo(s))"
    )