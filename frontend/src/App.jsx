
import { useState } from 'react'
import './App.css'

function App() {
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState([])

  
async function sendMessage() {
  if (!message.trim()) return

  const userMessage = message

  setMessages(prev => [
    ...prev,
    { role: 'user', content: userMessage }
  ])

  setMessage('')

  try {
    const response = await fetch('http://127.0.0.1:8080/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: userMessage
      })
    })

    if (!response.ok) {
      throw new Error('Lỗi từ Backend')
    }

    const data = await response.json()

    setMessages(prev => [
      ...prev,
      { role: 'assistant', content: data.reply }
    ])

  } catch (error) {
    console.error(error)
    setMessages(prev => [
      ...prev,
      { role: 'assistant', content: 'Không thể kết nối Backend!' }
    ])
  }
}


  return (
    <div className="app">

      {/* Thanh bên trái */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>My ChatGPT</h2>
          <button onClick={() => setMessages([])}>＋</button>
        </div>

        <button
          className="new-chat"
          onClick={() => setMessages([])}
        >
          ＋ Cuộc trò chuyện mới
        </button>

        <div className="history">
          <p>Hôm nay</p>
          {messages.length > 0 && (
            <div className="history-item">
              Cuộc trò chuyện mới
            </div>
          )}
        </div>

        <div className="profile">
          <div className="avatar">K</div>
          <span>My Account</span>
        </div>
      </aside>

      {/* Khu vực chat */}
      <main className="main">

        <header className="topbar">
          <span>Chatbot</span>
          <button>Chia sẻ</button>
        </header>

        <div className="chat-area">

          {messages.length === 0 ? (
            <div className="welcome">
              <h1>Bạn muốn hỏi điều gì?</h1>
              <p>Hãy bắt đầu cuộc trò chuyện với chatbot của bạn.</p>
            </div>
          ) : (
            <div className="messages">
              {messages.map((item, index) => (
                <div key={index} className={`message ${item.role}`}>
                  {item.content}
                </div>
              ))}
            </div>
          )}

        </div>

        {/* Ô nhập tin nhắn */}
        <div className="input-container">
          <div className="input-box">
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  sendMessage()
                }
              }}
              placeholder="Nhắn tin cho chatbot..."
              rows="1"
            />

            <button
              className="send-button"
              onClick={sendMessage}
            >
              ↑
            </button>
          </div>

          <p className="disclaimer">
            Chatbot đang trong quá trình phát triển.
          </p>
        </div>

      </main>
    </div>
  )
}

export default App
