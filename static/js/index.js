let sessionId = null;

        // Función para iniciar la sesión automáticamente
        async function startSession() {
            //Llamada a la API para iniciar la sesión. /start_session es la ruta definida en el servidor (main.py)
            const response = await fetch('/start_session', {
                method: 'POST'
            });
            const data = await response.json();
            sessionId = data.session_id;
            console.log("Sesión iniciada con ID:", sessionId);
        }

        // Función para enviar mensajes
        async function sendMessage() {
            const userInput = document.getElementById("user-input").value;
            if (userInput.trim() === "") return;

            // Añadir el mensaje del usuario al contenedor de chat
            addMessage(userInput, 'user');

            // Llamada a la API para enviar el mensaje del usuario. /chat es la ruta definida en el servidor (main.py)
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ user_input: userInput, session_id: sessionId }),
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                console.error("Error:", errorData.detail);
                return;
            }

            const data = await response.json();

            // Añadir la respuesta del chatbot al contenedor de chat
            addMessage(data.response, 'bot');

            // Limpiar el campo de entrada
            document.getElementById("user-input").value = "";
        }

        // Función para añadir un mensaje al contenedor de chat
        function addMessage(text, sender) {
            const chatContainer = document.getElementById("chat-container");
            const messageDiv = document.createElement("div");
            messageDiv.classList.add("message", sender);
            messageDiv.textContent = text;
            chatContainer.appendChild(messageDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight; // Desplazarse al final del contenedor
        }

        // Iniciar sesión simplemente al cargar la página
        startSession();