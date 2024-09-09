let sessionId = null;

// Lista de mensajes especiales que requieren un comportamiento específico
const specialTags = {
    "loading-db:start": handleLoadingDbStart, // Arranque de la animación de carga para búsquedas en la base de datos
    "loading-db:end": handleLoadingDbEnd,  // Fin de la animación de carga para búsquedas en la base de datos
};

// ---------------------CALLBACKS---------------------
// Función para manejar "loading-db:start"
function handleLoadingDbStart() {
    const chatContainer = document.getElementById('chat-container');
    //Contenedor de la animación de carga
    const div = document.createElement('div');
    div.id = 'loading-div';

    // Crear el mensaje de carga
    const text = document.createElement('p');
    text.id = 'loading-text';
    text.textContent = "Buscando tu piso ideal...";
    div.appendChild(text);

    // Añadir una animación de tipo spinning
    const spinner = document.createElement('span');
    spinner.id = 'loading-spinner';
    div.appendChild(spinner);

    chatContainer.appendChild(div);
}

// Función para manejar "loading-db:end"
function handleLoadingDbEnd() {
    // Eliminar el div de animación de carga
    const div = document.getElementById('loading-div');
    if (div) {
        div.remove();
    }
}


// --------------------- FUNCIONALIDAD DE LOS ENLACES ---------------------
// Función para devolver un enlace html a partir de una URL
function createUrlLink(url) {
    const link = document.createElement('a');
    link.href = url;
    link.textContent = url;
    link.target = '_blank';  // Para que el enlace se abra en una nueva pestaña
    return link;
}


// ---------------------FUNCIONALIDAD DEL CHATBOT---------------------
// INICIO DE SESIÓN
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

// ENVÍO Y RECEPCIÓN DE MENSAJES
async function sendMessage() {

    if (!sessionId) {
        console.error("Session ID is missing.");
        return;
    }

    // Recoge el input del cliente y comprueba si está vacío
    const userInput = document.getElementById("user-input").value;
    if (userInput.trim() === "") return;

    // Añadir el mensaje del usuario al contenedor de chat
    let is_new_message = true; // Variable para controlar si se ha creado un nuevo contenedor de mensajes
    addMessage(userInput, 'user', is_new_message); 

    // Llamada a la API para enviar el mensaje del usuario. /chat es la ruta definida en el servidor (main.py)
    try {
        response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ user_input: userInput, session_id: sessionId }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error("ERROR: API response error", errorData.detail);
            return;
        }
        
        // Leer la respuesta de la API como un stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        // Leer el stream de datos progresivamente. Este bucle se mantiene mientras sigan llegando mensajes del backend
        while (true) {
            const {done, value} = await reader.read();
            if (done) break;

            // Decodificar la respuesta del stream
            let chunk = decoder.decode(value, { stream: true });
            console.log("CHUNK:", chunk);

            // Verificar si hay tags especiales y eliminarlos del chunk
            const specialTagKeys = Object.keys(specialTags);
            let remainingChunk = chunk;

            specialTagKeys.forEach(tag => {
                if (remainingChunk.includes(tag)) {
                    // Ejecutar la función asociada al tag especial
                    specialTags[tag]();
            
                    // Eliminar todas las ocurrencias del tag en el chunk
                    remainingChunk = remainingChunk.split(tag).join('');
                }
            });

             // Verificar si el chunk contiene una URL
            const urlPattern = /(https?:\/\/[^\s]+)/g;
            const chunkParts = remainingChunk.split(urlPattern);
            is_new_message = true 
            
            for (const part of chunkParts) {
                if (urlPattern.test(part)) {
                    // Si el fragmento es una URL, se llama a la función para crear el enlace
                    link = createUrlLink(part);
                    addMessage(link, "bot", is_new_message)
                    addMessage("br", "bot", is_new_message);
                    addMessage("br", "bot", is_new_message);
                    is_new_message = false; 
                } else {
                    // Aquí se procesa cada respuesta parcial que no tenga un trato especial (que sea simple texto) generando un flujo de texto
                    const textParts = part.match(/.{1,3}/g) || []; //Fragmentamos el texto restante en partes de 3 caracteres
                    for (const textPart of textParts) {
                        if (textPart.trim() !== "") {
                            addMessage(textPart, "bot", is_new_message);
                            is_new_message = false; 
                            // Simular un pequeño retraso para el efecto de flujo
                            await new Promise(resolve => setTimeout(resolve, 20));
                        }
                    }
                    if (textParts.some(tp => tp.trim() !== "")) {
                        addMessage("br", "bot", is_new_message);
                        addMessage("br", "bot", is_new_message);
                    }
                }
            }
            is_new_message = true
        }
    } catch (error) {
        console.error("Error en la comunicación con la API:", error);
        addMessage(error, 'bot');
    } finally {
        // Limpiar el campo de entrada
        document.getElementById("user-input").value = "";
    }
}


// CREAR CONTENEDOR DE MENSAJES
// Esta función crea un nuevo contenedor de mensajes y si ya se ha creado añade nuevos mensajes sin sobreescribir los anteriores
function addMessage(content, sender, is_new_message = true) {
    let messageDiv = null;
    const chatContainer = document.getElementById("chat-container");

    if (is_new_message) {
        if (sender === "bot" || sender === "welcome") {
            // Llamamos a la función para crear la estructura del mensaje del chatbot
            messageDiv = createBotMessageContainer(sender);
        } else {
            // Crear un nuevo contenedor de mensaje si es el usuario u otro remitente
            messageDiv = document.createElement("div");
            messageDiv.classList.add("message", sender);
        }
        chatContainer.appendChild(messageDiv);
    } else {
        // Seleccionar el último contenedor de mensajes del mismo remitente
        const allMessages = chatContainer.querySelectorAll(".message." + sender);
        messageDiv = allMessages[allMessages.length - 1];
    }

    // Si el remitente es el bot, añadir el contenido al sub-div "bot-message-content"
    let targetDiv = messageDiv;
    if (sender === "bot" || sender === "welcome") {
        targetDiv = messageDiv.querySelector(".bot-message-content");
    }

    // Si el contenido es un elemento HTML, lo añadimos directamente
    if (content instanceof HTMLElement) {
        targetDiv.appendChild(content);
    } else if (content === "br") {
        // Añadir un salto de línea si el contenido es "br"
        const lineBreak = document.createElement("br");
        targetDiv.appendChild(lineBreak);
    } else {
        // Si es texto, crear un nodo de texto
        const textNode = document.createTextNode(content);
        targetDiv.appendChild(textNode);
    }
    
    scrollToBottom(); // Desplazarse al final del contenedor
}


// ESTRUCTURA DEL CONTENEDOR DEL MENSAJE DEL BOT
function createBotMessageContainer(sender) {
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", sender);

    // Crear el contenedor del logo
    const logoContainer = document.createElement("div");
    logoContainer.classList.add("bot-logo-container");

    // Crear la imagen del logo
    const logo = document.createElement("img");
    logo.src = "static/bot-logo.png";
    logo.alt = "Bot logo";
    logo.classList.add("bot-logo");

    // Añadir la imagen del logo al contenedor
    logoContainer.appendChild(logo);

    // Crear el contenedor del mensaje
    const messageContent = document.createElement("div");
    messageContent.classList.add("bot-message-content");

    // Añadir el contenedor del logo y el contenedor del mensaje a messageDiv
    messageDiv.appendChild(logoContainer);
    messageDiv.appendChild(messageContent);

    return messageDiv;
}


// DESPLAZARSE AL FINAL DEL CONTENEDOR DE CHAT
function scrollToBottom() {
    const chatContainer = document.getElementById("chat-container");
    chatContainer.scrollTop = chatContainer.scrollHeight;
}


// MENSAJE DE BIENVENIDA
async function fetchWelcomeMessage() {
    try {
        const response = await fetch('/welcome-message'); // La ruta del endpoint del mensaje de bienvenida
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const data = await response.json();
        addMessage(data.message, 'welcome'); // Añadir el mensaje de bienvenida al chat
    } catch (error) {
        console.error("Error fetching welcome message:", error);
        addMessage("Error: Could not load welcome message.", 'bot');
    }
}


// ARRANCAR EL CHATBOT
async function initiateSession() {
    await startSession()
    await fetchWelcomeMessage(); // Cargar y mostrar el mensaje de bienvenida
}


// CARGA DE LA WEB
document.addEventListener('DOMContentLoaded', initiateSession);