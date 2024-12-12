let sessionId = null;
let markdownBuffer = '';  // Buffer que almacena el markdown completo.
let tempSpan = null;  // Variable para el span temporal.


// ---------------------CALLBACKS---------------------
// Lista de mensajes especiales que requieren un comportamiento específico
const specialTags = {
    "loading-db:start": handleLoadingDbStart, // Arranque de la animación de carga para búsquedas en la base de datos
    "loading-db:end": handleLoadingDbEnd,  // Fin de la animación de carga para búsquedas en la base de datos
};

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
    if (event.key === 'Enter' && input.trim() !== '') {
        sendMessage(input);
    }
});


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
        console.error("Error al iniciar la sesión: ", error);
        const errorMessageDiv = createBotMessageContainer('bot');
        const chatContainer = document.getElementById("chat-container");
        targetDiv = errorMessageDiv.querySelector(".bot-message-content");
        targetDiv.insertAdjacentHTML('beforeend', `Error: ${error.message}`);
        chatContainer.appendChild(errorMessageDiv);
    }
}

// ENVÍO Y RECEPCIÓN DE MENSAJES
async function sendMessage(userInput) {

    // 1. Validación inicial
    if (!sessionId) {
        console.error("Session ID is missing.");
        return;
    }
    if (userInput.trim() === "") return;

    // 2. Mostrar el mensaje del usuario
    document.getElementById("user-input").value = "";
    const userMessageDiv = createUserMessageContainer(userInput);
    document.getElementById("chat-container").appendChild(userMessageDiv);

    // 3. Creación del contenedor para el mensaje del bot
    messageDiv = createBotMessageContainer("bot");
    document.getElementById("chat-container").appendChild(messageDiv);
    targetDiv = messageDiv.querySelector(".bot-message-content");

    try {
        // 5. Solicitud de mensaje al backend
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ user_input: userInput }),
        });

        // 6. Validación de la solicitud
        if (!response.ok) {
            const errorData = await response.json();
            console.error("ERROR: API response error", errorData.detail);
            return;
        }

        // 7. Lectura del stream de datos
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        botMessage = ""

        // 8. Bucle de lectura mientras el stream reciba datos
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            let chunk = decoder.decode(value, { stream: true }); // Convertir datos binarios a texto.
            botMessage+= chunk

            // 9. Bucle de lectura mientras el stream reciba datos
            const specialTagKeys = Object.keys(specialTags);
            specialTagKeys.forEach(tag => {
                if (chunk.includes(tag)) {
                    specialTags[tag]();  // Ejecutar la función asociada al comando
                    chunk = chunk.split(tag).join('');  // Eliminar el comando del chunk
                }
            });
            // 10. Procesado del html
            await renderize_html(chunk);
        }
        scrollToBottom()
    } catch (error) {
        targetDiv.insertAdjacentHTML('beforeend', `Error: ${error.message}`);
    }
    finally {
        await cleanTemporalSpan();
    }
}

//___________________________________________________________________

async function renderize_html(chunk) {
    // Eliminar elementos markdown del chunk (simplificación)
    const plainText = chunk.replace(/[#*_\[\]\(\)`]/g, '');

    // Si no existe un span temporal, lo creamos.
    if (!tempSpan) {
        tempSpan = document.createElement('span');
        tempSpan.className = 'temp-span';
        targetDiv.appendChild(tempSpan);
    }

    // Insertamos el texto plano en el span temporal.
    tempSpan.innerText += plainText;

    // Añadimos el chunk completo (con markdown) al buffer.
    markdownBuffer += chunk;

    // Verificamos si hemos llegado al final de una estructura markdown.
    if (isCompleteMarkdown(markdownBuffer)) {
        // Si el markdown está completo, renderizamos el HTML final.
        renderFinalHTML();
    }
}

// Detectar si el markdown está completo.
function isCompleteMarkdown(buffer) {
    // Aquí definimos los criterios para determinar si el bloque markdown está completo.
    // Por ejemplo, puedes verificar por saltos de línea dobles o cierres de etiquetas markdown.
    const closingTags = ['\n\n', '</ul>', '</ol>', '</h1>', '</h2>', '</p>'];
    return closingTags.some(tag => buffer.includes(tag));
}

// Función para eliminar el span temporal y sustituirlo por el contenido renderizado.
function renderFinalHTML() {
    if (tempSpan) {
        // Eliminamos el span temporal.
        targetDiv.removeChild(tempSpan);
        tempSpan = null;
    }

    // Convertimos el contenido markdown acumulado en HTML usando marked.js
    const renderedHTML = marked.parse(markdownBuffer);

    // Insertamos el HTML renderizado en el targetDiv.
    targetDiv.innerHTML += renderedHTML;

    // Limpiamos el buffer después de renderizar.
    markdownBuffer = '';

    scrollToBottom();
}

async function cleanTemporalSpan() {
    tempSpan = null;
    markdownBuffer = "";
    // Selecciona todos los elementos con la clase 'temp-span'
    const tempSpans = document.querySelectorAll('span.temp-span');

    // Itera sobre cada elemento encontrado
    tempSpans.forEach(tempSpan => {
        // Crea un nuevo elemento <p>
        const pElement = document.createElement('p');
        
        // Copia el contenido del <span> en el nuevo <p>
        pElement.innerHTML = tempSpan.innerHTML;
        
        // Reemplaza el <span> con el nuevo <p>
        tempSpan.parentNode.replaceChild(pElement, tempSpan);
    });
}
//___________________________________________________________________

// ESTRUCTURA DEL CONTENEDOR DEL MENSAJE DEL USUARIO
function createUserMessageContainer(messageContent) {
    // Crear el div del mensaje del usuario
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", "user"); // Añadir las clases "message" y "user"

    // Crear el nodo de texto para el mensaje del usuario
    const textNode = document.createTextNode(messageContent);

    // Añadir el texto al contenedor del mensaje
    messageDiv.appendChild(textNode);

    return messageDiv;
}

// ESTRUCTURA DEL CONTENEDOR DEL MENSAJE DEL BOT
function createBotMessageContainer() {
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", "bot");

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

    scrollToBottom()

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

        // Crear el contenedor del mensaje de bienvenida
        const welcomeMessageDiv = createBotMessageContainer();
        const chatContainer = document.getElementById("chat-container");
        const targetDiv = welcomeMessageDiv.querySelector(".bot-message-content");
        targetDiv.insertAdjacentHTML('beforeend', data.message);
        chatContainer.appendChild(welcomeMessageDiv);

    } catch (error) {
        console.error("Error fetching welcome message:", error);

        // Crear un contenedor para el mensaje de error en caso de fallo
        const errorMessageDiv = createBotMessageContainer();
        const chatContainer = document.getElementById("chat-container");
        const targetDiv = errorMessageDiv.querySelector(".bot-message-content");

        // Añadir el mensaje de error al div correspondiente
        targetDiv.insertAdjacentHTML('beforeend', "Error: Could not load welcome message.");

        // Añadir el contenedor de error al chat
        chatContainer.appendChild(errorMessageDiv);
    }
}


// ARRANCAR EL CHATBOT
async function initiateSession() {
    await startSession()
    await fetchWelcomeMessage(); // Cargar y mostrar el mensaje de bienvenida
}


// CARGA DE LA WEB
document.addEventListener('DOMContentLoaded', initiateSession);