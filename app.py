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
st.set_page_config(page_title="Meta Ads Assistant", layout="centered")
st.title("📊 Meta Ads Assistant")
st.write("Ask me anything about your Meta Ads performance.")

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "Hi! I'm your Meta Ads assistant. How can I help today?"}
    ]

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User input handling
if user_input := st.chat_input("Ask a question..."):
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = client.beta.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=20000,
                    messages=st.session_state.chat_history,
                    mcp_servers=[{
                        "type": "url",
                        "url": f"{MCP_URL}/mcp/",
                        "name": "meta-ads"
                    }],
                    extra_headers={"anthropic-beta": "mcp-client-2025-04-04"}
                )
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"Error: {e}"
                })
                

        # Display Claude's response in collapsible sections
        block_index = 1
        for block in response.content:
            label = f"Block {block_index}: "
            block_index += 1

            if hasattr(block, "text"):
                with st.expander(label + "Text"):
                    st.markdown(block.text)

            elif hasattr(block, "content"):  # Tool result block
                with st.expander(label + "Tool Result"):
                    for sub_block in block.content:
                        if hasattr(sub_block, "text"):
                            st.markdown(sub_block.text)

            elif hasattr(block, "name") and hasattr(block, "input"):  # Tool call block
                with st.expander(label + f"Tool Call: `{block.name}`"):
                    st.markdown("**Input Parameters:**")
                    st.json(block.input)

            else:
                with st.expander(label + "Unknown Block"):
                    st.write(block)

        # Store placeholder for this assistant reply
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "(response displayed above)"
        })
