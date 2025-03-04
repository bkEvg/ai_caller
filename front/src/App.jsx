import { useState } from "react";

function App() {
  const [phone, setPhone] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    console.log("Отправляем номер:", phone);

    try {
      const response = await fetch("http://217.114.9.31:4040/api/v1/calls", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ phone }),
      });

      if (response.ok) {
        alert("Номер отправлен!");
      } else {
        alert("Ошибка при отправке!");
      }
    } catch (error) {
      console.error("Ошибка запроса:", error);
      alert("Ошибка соединения!");
    }
  };

  return (
    <div style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      height: "100vh",
      width: "100vw",
      backgroundColor: "#f4f4f4",
      padding: "20px",
      boxSizing: "border-box"
    }}>
      <div style={{
        width: "100%",
        maxWidth: "400px",
        padding: "20px",
        background: "#fff",
        boxShadow: "0 4px 8px rgba(0, 0, 0, 0.1)",
        borderRadius: "8px",
        textAlign: "center"
      }}>
        <h2>Сделать звонок на номер</h2>
        <form onSubmit={handleSubmit}>
          <input
            type="tel"
            placeholder="+7 (999) 123-45-67"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            style={{
              width: "100%",
              paddingTop: "10px",
              paddingBottom: "10px",
              fontSize: "16px",
              marginBottom: "10px",
              borderRadius: "4px",
              border: "1px solid #ccc"
            }}
            required
          />
          <button type="submit" style={{
            width: "100%",
            padding: "10px",
            fontSize: "16px",
            border: "none",
            backgroundColor: "#007bff",
            color: "#fff",
            borderRadius: "4px",
            cursor: "pointer"
          }}>
            Позвонить
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;