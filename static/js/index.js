let sessionId = null;

        // Función para iniciar la sesión automáticamente
        async function startSession() {
            try {
                const response = await fetch('/start_session', {
                    method: 'POST'
                });
                const data = await response.json();
                sessionId = data.session_id;
                console.log("Sesión iniciada con ID:", sessionId);
            } catch (error) {
                console.error("Error al iniciar la sesión:", error);
                addMessage("Error al iniciar la sesión", 'bot');
            }
        }


        // Función para enviar mensajes
        async function sendMessage() {

            if (!sessionId) {
                console.error("Session ID is missing.");
                return;
            }
            
            // Recoge el input del cliente y comprueba si está vacío
            const userInput = document.getElementById("user-input").value;
            if (userInput.trim() === "") return;

            // Añadir el mensaje del usuario al contenedor de chat
            addMessage(userInput, 'user');

            // Llamada a la API para enviar el mensaje del usuario. /chat es la ruta definida en el servidor (main.py)
            try{
                let response = null
                try{
                    response = await fetch('/chat', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ user_input: userInput, session_id: sessionId }),
                    });
                }catch(error){
                    console.error("Error en la recogida de datos de la API:", error);
                    addMessage("Error en la recogida de datos de la API:", 'bot');
                }
            
                if (!response.ok) {
                    const errorData = await response.json();
                    console.error("Error:", errorData.detail);
                    return;
                }

                // Usar ReadableStream para manejar la respuesta de flujo
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let botMessage = '';
                let messageDiv = createMessageElement('bot');

                // Leemos el stream de datos
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    // Decodificamos los bytes y añadimos el texto al mensaje del bot
                    botMessage += decoder.decode(value, { stream: true });
                    
                    // Actualizamos el mensaje progresivamente en el contenedor de chat
                    messageDiv.textContent = botMessage;
                    scrollToBottom();
                }

            } catch (error) {
                console.error("Error en la comunicación con la API:", error);
                addMessage(error, 'bot');
            } finally {
                // Limpiar el campo de entrada
                document.getElementById("user-input").value = "";
            }
        }


        // Función para añadir un mensaje al contenedor de chat
        function addMessage(text, sender) {
            const chatContainer = document.getElementById("chat-container");
            const messageDiv = createMessageElement(sender);
            messageDiv.textContent = text;
            chatContainer.appendChild(messageDiv);
            scrollToBottom(); // Desplazarse al final del contenedor
        }


        // Función para crear el elemento de mensaje
        function createMessageElement(sender) {
            const chatContainer = document.getElementById("chat-container");
            const messageDiv = document.createElement("div");
            messageDiv.classList.add("message", sender);
            chatContainer.appendChild(messageDiv);
            return messageDiv;
        }


        // Función para desplazarse al final del contenedor de chat
        function scrollToBottom() {
            const chatContainer = document.getElementById("chat-container");
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }


        // Función para obtener el mensaje de bienvenida del servidor
        async function fetchWelcomeMessage() {
            try {
                const response = await fetch('/welcome-message'); // La ruta del endpoint del mensaje de bienvenida
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                const data = await response.json();
                addMessage(data.message, 'bot'); // Añadir el mensaje de bienvenida al chat
            } catch (error) {
                console.error("Error fetching welcome message:", error);
                addMessage("Error: Could not load welcome message.", 'bot');
            }
        }


        // Función para iniciar la sesión del chatbot
        async function initiateSession() {
            await startSession()
            await fetchWelcomeMessage(); // Cargar y mostrar el mensaje de bienvenida
        }


        // Iniciar sesión cuando la página se carga
        document.addEventListener('DOMContentLoaded', initiateSession);