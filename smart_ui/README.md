# Smart UI

`smart_ui` combines:

- AI logic from `../ai/test_ui.py` (wake word, listening, routing, TTS, follow-up behavior)
- Visual UI from `../ui` screens

Only the UI layer is swapped; assistant behavior remains from the updated `ai` code.

## Run

From project root:

```bash
cd smart_ui
../ai/venv313/bin/python main.py
```

If you normally run with environment variables (API keys, manual mode, etc.), set them exactly the same way as with the `ai` app before starting.
