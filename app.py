import streamlit as st
import anthropic
import os

# Load secrets securely
API_KEY = st.secrets["claude"]["api_token"]
MCP_URL = st.secrets["pipeboard"]["url"]
os.environ["PIPEBOARD_API_TOKEN"] = st.secrets["pipeboard"]["api_token"]

# Initialize Claude client
client = anthropic.Anthropic(api_key=API_KEY)

# Streamlit UI setup
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
                    messages=[
                        {"role": "user", "content": user_input}
                    ],
                    mcp_servers=[{
                        "type": "url",
                        "url": f"{MCP_URL}/mcp/",
                        "name": "meta-ads"
                    }],
                    extra_headers={"anthropic-beta": "mcp-client-2025-04-04"}
                )

                # Combine all text from the response into a single string
                reply = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        reply += f"{block.text}\n\n"
                    elif hasattr(block, "content"):
                        for sub_block in block.content:
                            if hasattr(sub_block, "text"):
                                reply += f"{sub_block.text}\n\n"

            except Exception as e:
                reply = f"❌ Error: {e}"

        st.markdown(reply)
