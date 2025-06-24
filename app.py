import streamlit as st
import anthropic

# Load Claude API key securely from secrets
API_KEY = "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"

# Initialize Claude client
client = anthropic.Anthropic(api_key=API_KEY)

st.set_page_config(page_title="Meta Ads Chat", layout="centered")
st.title("📊 Meta Ads Chat Assistant")
st.write("Ask me anything about your Meta Ads performance.")

# Chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "Hi! I'm your Meta Ads assistant. How can I help today?"}
    ]

# Display chat
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
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
                        "url": "https://your-meta-ads-mcp.onrender.com/mcp/",
                        "name": "meta-ads"
                    }],
                    extra_headers={"anthropic-beta": "mcp-client-2025-04-04"}
                )
                reply = response.content[0].text
            except Exception as e:
                reply = f"❌ Error: {e}"

        st.markdown(reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
