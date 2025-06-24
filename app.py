import streamlit as st
import anthropic
import os

# Load secrets
API_KEY = st.secrets["claude"]["api_token"]
MCP_URL = st.secrets["pipeboard"]["url"]
os.environ["PIPEBOARD_API_TOKEN"] = st.secrets["pipeboard"]["api_token"]

# Initialize Claude client
client = anthropic.Anthropic(api_key=API_KEY)

# Streamlit setup
st.set_page_config(page_title="Meta Ads Chat", layout="centered")
st.title("📊 Meta Ads Assistant")
st.write("Ask me anything about your Meta Ads performance.")

# Chat input
if user_input := st.chat_input("Ask a question..."):
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = client.beta.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=20000,
                    messages=[{"role": "user", "content": user_input}],
                    mcp_servers=[{
                        "type": "url",
                        "url": f"{MCP_URL}/mcp/",
                        "name": "meta-ads"
                    }],
                    extra_headers={"anthropic-beta": "mcp-client-2025-04-04"}
                )

                # Find the last BetaTextBlock
                last_text = ""
                for block in reversed(response.content):
                    if hasattr(block, "text"):
                        last_text = block.text
                        break
                    elif hasattr(block, "content"):
                        for sub_block in reversed(block.content):
                            if hasattr(sub_block, "text"):
                                last_text = sub_block.text
                                break
                    if last_text:
                        break

            except Exception as e:
                last_text = f"❌ Error: {e}"

        st.markdown(last_text)
