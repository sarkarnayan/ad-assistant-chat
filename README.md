# ad-assistant-chat

Streamlit chat app for Meta Ads analysis using DeepInfra and a remote Pipeboard MCP server.

## Secrets

Configure Streamlit secrets with the DeepInfra API key, the target model, and the Pipeboard MCP endpoint:

```toml
[deepinfra]
api_token = "YOUR_DEEPINFRA_API_KEY"
model = "meta-llama/Meta-Llama-3.1-70B-Instruct"
max_tokens = 2000

[pipeboard]
url = "https://your-pipeboard-host"
api_token = "YOUR_PIPEBOARD_TOKEN"
```

Environment variable fallbacks are also supported:

- `DEEPINFRA_API_TOKEN`
- `DEEPINFRA_MODEL`
- `DEEPINFRA_MAX_TOKENS`
- `PIPEBOARD_URL`
- `PIPEBOARD_API_TOKEN`
