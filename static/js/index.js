let sessionId = null;
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
        console.error("Error al iniciar la sesión: ", error);
        const errorMessageDiv = createBotMessageContainer('bot');
        const chatContainer = document.getElementById("chat-container");
        const targetDiv = errorMessageDiv.querySelector(".bot-message-content");
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
    let messageDiv = createBotMessageContainer("bot");
    document.getElementById("chat-container").appendChild(messageDiv);
    let targetDiv = messageDiv.querySelector(".bot-message-content");

    /*
    1 - Detectar cuándo comienza una etiqueta HTML con <.
    2 - Crear un contenedor temporal <span id="temporal_id"> donde se mostrarán de forma instantánea los caracteres a medida que llegan.
    3 - Detectar cuándo la etiqueta de apertura está completa (cuando se reciba >).
    4 - A partir de ahí, continuar mostrando los caracteres dentro del span, pero también acumularlos en un buffer.
    5 - Detectar cuándo se completa una etiqueta de cierre.
    6 - Una vez que se completa la etiqueta de cierre, eliminar el span temporal y sustituir su contenido con el HTML completo renderizado.
    */

    // 4. Instanciar variables
    let partialTag = ""; // Acumula fragmentos de HTML incompleto.
    let accumulatedMessage = ""; // Buffer para el HTML completo.
    let isInsideTag = false; // Indica si estamos dentro de una etiqueta HTML.
    let insideTagBuffer = ""; // Acumula los caracteres de una etiqueta HTML.
    let isRendering = false; // Indica si estamos mostrando un span temporal.
    let botMessage = "";

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

        // 8. Bucle de lectura mientras el stream reciba datos
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            let chunk = decoder.decode(value, { stream: true }); // Convertir datos binarios a texto.
            console.log("CHUNK: " + chunk);

            // 9. Bucle de lectura mientras el stream reciba datos
            const specialTagKeys = Object.keys(specialTags);
            specialTagKeys.forEach(tag => {
                if (chunk.includes(tag)) {
                    specialTags[tag]();  // Ejecutar la función asociada al comando
                    chunk = chunk.split(tag).join('');  // Eliminar el comando del chunk
                }
            });



















            // Procesar el chunk carácter por carácter
            for (let i = 0; i < chunk.length; i++) {
                const char = chunk[i];
                botMessage+=char

                // Si detectamos el inicio de una etiqueta "<"
                if (char === "<") {
                    isInsideTag = true;
                    insideTagBuffer = "<";

                    // Si no estamos renderizando, añadimos el span temporal
                    if (!isRendering) {
                        targetDiv.insertAdjacentHTML('beforeend', '<span id="temporal_id"></span>');
                        isRendering = true;
                    }
                } else if (isInsideTag) {
                    // Continuamos acumulando la etiqueta dentro del buffer
                    insideTagBuffer += char;

                    // Si encontramos el final de la etiqueta de apertura ">"
                    if (char === ">") {
                        isInsideTag = false;

                        // Añadimos el contenido del buffer al HTML acumulado
                        partialTag += insideTagBuffer;
                        insideTagBuffer = "";

                        // Terminamos de mostrar el contenido en el span temporal
                        const tempSpan = document.getElementById("temporal_id");
                        if (tempSpan) {
                            tempSpan.insertAdjacentHTML('beforeend', partialTag);
                        }
                    }
                } else {
                    // Si estamos fuera de una etiqueta, mostramos el carácter directamente en el span
                    const tempSpan = document.getElementById("temporal_id");
                    if (tempSpan) {
                        tempSpan.insertAdjacentHTML('beforeend', char);
                    }

                    // También acumulamos el mensaje completo
                    partialTag += char;
                }

                // Detectar etiquetas de cierre
                if (partialTag.includes("</")) {
                    const closingTagIndex = partialTag.indexOf(">");
                    if (closingTagIndex !== -1) {
                        // Eliminar el span temporal y renderizar el HTML completo
                        const tempSpan = document.getElementById("temporal_id");
                        if (tempSpan) {
                            tempSpan.remove();
                        }

                        // Añadir el HTML completo al DOM
                        targetDiv.insertAdjacentHTML('beforeend', partialTag);
                        partialTag = ""; // Resetear el buffer
                        isRendering = false;
                    }
                }
            }
        }

        // 12. Finalización del procesamiento
        if (partialTag.trim() !== "") {  // En caso de que hayan quedado secciones de HTML sin renderizar
            accumulatedMessage += partialTag;
            partialTag = "";
        }

    } catch (error) {
        targetDiv.insertAdjacentHTML('beforeend', `Error: ${error.message}`);
    } finally {
        await updateSession(userInput, botMessage); // Enviar el mensaje completo para actualizar la sesión
        console.log("MENSAJE COMPLETO: "+ botMessage)
    }
}


    let inside_tag = false // Estamos procesando una etiqueta html
    let creating_message = true // Estamos mostrando contenido sin renderizar el html
    let tag_buffer= "" // código html de la etiqueta
    let complete_html_message = ""
    
async function renderize_html(chunk){
    
    for (let i = 0; i < chunk.length; i++){
        const char = chunk[i];
        if(char ==="<"){
            inside_tag = true
            tag_buffer = "<"
            for (let j = i; j < chunk.length; j++)
                if(creating_message && chunk[i+1]=="<"){
                    renderize_html(chunk[j])
                }
            if (!creating_message) {
                targetDiv.insertAdjacentHTML('beforeend', '<span id="temporal_id"></span>');
                creating_message = false;
            }
        } else if (inside_tag) {
            tag_buffer+= char
            if (char === ">") {
                inside_tag = false;
                complete_html_message+=tag_buffer
                tag_buffer=""
            }
        } else {

        }
    }
}


// ACTUALIZACIÓN DE LA SESIÓN
async function updateSession(userInput, botResponse) {
    try {
        const response = await fetch('/update_session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_input: userInput,
                bot_response: botResponse 
            }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error("ERROR: API response error", errorData.detail);
            return;
        }

        console.log("Sesión actualizada con éxito");
    } catch (error) {
        console.error("Error al actualizar la sesión:", error);
    }
}

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