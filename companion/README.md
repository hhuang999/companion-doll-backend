# companion-backend

Python 3.10 情感陪伴玩偶后端。包含独立 CLI、Talker / Reasoner、确定性许可状态、风险接管、练习计划、SQLite 记忆和 Streamlit 看板。

```sh
python -m pip install -e '.[test]'
companion --fake
companion --env-file /path/to/.env
companion-dashboard --db data/companion.db
pytest
```

默认 development 使用明确标记的开发夹具和待审核内容。正式材料和硬件联调要求见 `docs/CONTENT.md` 与 `docs/VALIDATION.md`。完整项目的 Windows 安装 / 运行脚本及小智补丁位于此包上层的项目仓库。
