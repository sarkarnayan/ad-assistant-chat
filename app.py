import streamlit as st
import anthropic
import os

# Load secrets
API_KEY = st.secrets["claude"]["api_token"]
MCP_URL = st.secrets["pipeboard"]["url"]
os.environ["PIPEBOARD_API_TOKEN"] = st.secrets["pipeboard"]["api_token"]

# Initialize Claude client
client = anthropic.Anthropic(api_key=API_KEY)

# UI setup
st.set_page_config(page_title="Meta Ads Chat", layout="centered")
st.title("📊 Meta Ads Assistant")
st.write("Ask me anything about your Meta Ads performance.")

# Handle user input
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

                # Iterate through all blocks
                for block in response.content:
                    # Show all text blocks directly
                    if hasattr(block, "text"):
                        st.markdown(block.text)

                    # If it's a tool result with nested text
                    elif hasattr(block, "content"):
                        with st.expander("🔧 Tool Result", expanded=False):
                            for sub_block in block.content:
                                if hasattr(sub_block, "text"):
                                    st.markdown(sub_block.text)

                    # Show tool usage (like get_ad_accounts, get_ads) in an expandable box
                    elif getattr(block, "type", "") == "mcp_tool_use":
                        with st.expander(f"⚙️ Tool Called: `{block.name}`", expanded=False):
                            st.markdown("**Input:**")
                            st.json(block.input)

            except Exception as e:
                st.error(f"❌ Error: {e}")
