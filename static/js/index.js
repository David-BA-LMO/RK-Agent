let sessionId = null;
let message_is_finish = true
let accumulatedMessage = "";  // Variable para acumular los fragmentos de texto.
let partialTag = "";  // Para manejar las etiquetas HTML incompletas.

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


// --------------------- ENVÍO DEL MENSAJE CON ENTER ---------------------
document.getElementById('user-input').addEventListener('keydown', function(event) {
    const input = document.getElementById('user-input').value;
    if (event.key === 'Enter' && input.trim() !== '' && message_is_finish) {
        sendMessage(input);
    }
});


// --------------------- AGREGAR ELEMENTO ENLACE ---------------------
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
        sessionId = data.session_id;  // Guardamos el session_id pasado al crear la sesión
    } catch (error) {
        console.error("Error al iniciar la sesión:", error);
        addMessage("Error al iniciar la sesión", 'bot');
    }
}

// ENVÍO Y RECEPCIÓN DE MENSAJES
async function sendMessage(userInput) {
    message_is_finish = false;

    if (!sessionId) {
        console.error("Session ID is missing.");
        return;
    }

    if (userInput.trim() === "") return;

    document.getElementById("user-input").value = "";

    let is_new_message = true;
    addMessage(userInput, 'user', is_new_message);

    try {
        response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({user_input: userInput}),
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error("ERROR: API response error", errorData.detail);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            let chunk = decoder.decode(value, { stream: true });
            console.log("CHUNK: "+chunk)

            // Verificar y ejecutar comandos especiales
            const specialTagKeys = Object.keys(specialTags);
            specialTagKeys.forEach(tag => {
                if (chunk.includes(tag)) {
                    specialTags[tag]();  // Ejecutar la función asociada al comando
                    chunk = chunk.split(tag).join('');  // Eliminar el comando del chunk
                }
            });

            is_new_message = true;

            // Procesar el texto restante después de eliminar comandos especiales
            const chunkParts = chunk.split(/(<[^>]*>|[^<]+)/); // Separar contenido HTML y texto
            for (const part of chunkParts) {
                const textParts = part.match(/.{1,3}/g) || []; // Fragmentamos en partes de 3 caracteres

                for (const textPart of textParts) {
                    partialTag += textPart;

                    // Intentar parsear para ver si tenemos un HTML válido
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = partialTag;

                    if (tempDiv.innerHTML !== partialTag) {
                        // El HTML no es válido todavía, seguimos acumulando
                        continue;
                    }

                    // HTML completo, agregar el mensaje
                    accumulatedMessage += partialTag;
                    partialTag = "";  // Limpiar la acumulación

                    addMessage(accumulatedMessage, "bot", is_new_message);
                    accumulatedMessage = "";  // Limpiar mensaje acumulado

                    await new Promise(resolve => setTimeout(resolve, 20)); // Efecto de flujo

                    if (is_new_message) {
                        is_new_message = false;
                    }
                }
            }

            if (partialTag.trim() !== "") {
                accumulatedMessage += partialTag;
                addMessage(accumulatedMessage, "bot", is_new_message);
                partialTag = "";
            }

            is_new_message = true;
            message_is_finish = true;
        }
    } catch (error) {
        console.error("Error en la comunicación con la API:", error);
        addMessage(error, 'bot');
    }
}

function addMessage(content, sender, is_new_message = true) {
    let messageDiv = null;
    const chatContainer = document.getElementById("chat-container");

    if (is_new_message) {
        if (sender === "bot" || sender === "welcome") {
            messageDiv = createBotMessageContainer(sender);
        } else {
            messageDiv = document.createElement("div");
            messageDiv.classList.add("message", sender);
        }
        chatContainer.appendChild(messageDiv);
    } else {
        const allMessages = chatContainer.querySelectorAll(".message." + sender);
        messageDiv = allMessages[allMessages.length - 1];
    }

    let targetDiv = messageDiv;
    if (sender === "bot" || sender === "welcome") {
        targetDiv = messageDiv.querySelector(".bot-message-content");
    }

    if (/<\/?[a-z][\s\S]*>/i.test(content)) {
        targetDiv.insertAdjacentHTML('beforeend', content);
    } else {
        const textNode = document.createTextNode(content);
        targetDiv.appendChild(textNode);
    }

    scrollToBottom();
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