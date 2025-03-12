import callbacks_functions from './callbacks.js';
import { createUserMessageContainer, createBotMessageContainer } from './messages.js';

let tempImageUrls = []; // Variable temporal para almacenar las imágenes recibidas
let markdownBuffer = '';  // Buffer que almacena el markdown csompleto.
let tempSpan = null;  // Variable para el span temporal.
let targetDiv = null;

// ---------------------FUNCIONALIDAD DEL CHATBOT---------------------
// INICIO DE SESIÓN
async function startSession() {
    try {
        const response = await fetch('/login', {
            method: 'POST'
        });
        const data = await response.json();
    } catch (error) {
        console.error("Error al iniciar la sesión: ", error);
        const errorMessageDiv = createBotMessageContainer('bot');
        const chatContainer = document.getElementById("chat-container");
        targetDiv = errorMessageDiv.querySelector(".bot-message-content");
        targetDiv.insertAdjacentHTML('beforeend', `Error: ${error.message}`);
        chatContainer.appendChild(errorMessageDiv);
    }
}

// ENVÍO DE MENSAJE DE TEXTO 
async function sendUserMessage(userInput) {
    if (userInput.trim() === "") return;

    // Limpiar el campo de entrada del usuario
    document.getElementById("user-input").value = "";
    
    // Crear y mostrar el mensaje del usuario en la interfaz
    createUserMessageContainer(userInput);

    // Crear la estructura del mensaje para enviar al backend
    const messageData = {
        type: "text",
        content: userInput
    };

    // Llamar a processMessage con los datos generados
    processMessage(messageData);
}


// PROCESADO DE DATOS EN BACKEND
async function processMessage(messageData) {
    try {

        if (!messageData){
            return
        }

        // Crear el contenedor del mensaje del bot en la interfaz
        let messageDiv = createBotMessageContainer("bot");
        document.getElementById("chat-container").appendChild(messageDiv);
        targetDiv = messageDiv.querySelector(".bot-message-content");

        // 5. Solicitud de mensaje al backend
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(messageData),
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
        let botMessage = ""

        // 8. Bucle de lectura mientras el stream reciba datos
        while (true) {
            const {done, value} = await reader.read();
            if (done) break;

            let chunk = decoder.decode(value, { stream: true });

            // 1. Dividir por líneas (cada línea debería ser un JSON chunk)
            const lines = chunk.split("\n").filter(line => line.trim() !== "");
            for (const line of lines) {
                try {
                    let data = ""
                    try {
                        data = JSON.parse(line);
                    } catch (error) {
                        console.error("Error al parsear JSON:", error.message);
                        console.error("JSON recibido:", line);
                    } // Parsear cada chunk como JSON

                    if (data.type === "text") { // Ejecución de texto
                        botMessage += data.content;
                        await renderize_html(data.content);

                    } else if (data.type === "image") { // Ejecución de imágenes (en URLs)
                        const imageUrl = data.content;
                        tempImageUrls.push(imageUrl)

                    } else if (data.type === "function") { // Ejecución de funciones
                        const functionName = data.content;
                        const functionInput = data.input;
                        
                        if (typeof callbacks_functions[functionName] === "function") {
                            if (functionInput !== undefined) {
                                const result = callbacks_functions[functionName](targetDiv, functionInput);
                                
                                if (result instanceof Promise) { // Si la función devuelve una promesa, esperar el resultado
                                    result.then(resolvedData => {
                                        console.log(resolvedData)
                                        processMessage(resolvedData); // Llamar recursivamente con el resultado
                                    }).catch(error => {
                                        console.error('Error en la ejecución de la función:', error);
                                    });
                                } else if (result) {
                                    processMessage(result);
                                }
                            } else {
                                const result = callbacks_functions[functionName](targetDiv);
                                
                                if (result instanceof Promise) { // Si la función devuelve una promesa, esperar el resultado
                                    result.then(resolvedData => {
                                        processMessage(resolvedData); // Llamar recursivamente con el resultado
                                    }).catch(error => {
                                        console.error('Error en la ejecución de la función:', error);
                                    });
                                } else if (result) {
                                    processMessage(result);
                                }
                            }
                        } else {
                            console.error(`La función '${functionName}' no está definida.`);
                        }
                    } else if (data.type === "coord") { // Ejecución de un mapa de posición
                        const [lon, lat] = data.content;
            
                        const mapDiv = document.createElement("div");
                        mapDiv.className = "map-container";
                        targetDiv.appendChild(mapDiv);
            
                        const map = L.map(mapDiv).setView([lat, lon], 13);
            
                        // Agregar una capa de mapa base (OpenStreetMap)
                        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                            attribution: '© OpenStreetMap contributors'
                        }).addTo(map);
            
                        // Agregar un marcador en las coordenadas especificadas
                        L.marker([lat, lon]).addTo(map)
                            .bindPopup(`Ubicación: ${lat}, ${lon}`)
                            .openPopup();
                    
                    } else if (data.type == "html"){

                    }
                } catch (error) {
                    console.error("Failed to parse chunk as JSON:", error);
                }
            }
        }
        if(tempImageUrls.length>0){
            console.log(tempImageUrls)
            callbacks_functions.generateImageCarrousel(targetDiv, tempImageUrls);
            tempImageUrls = []
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


// DESPLAZARSE AL FINAL DEL CONTENEDOR DE CHAT
function scrollToBottom() {
    const chatContainer = getLastBotMessageContent();
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
        targetDiv.insertAdjacentHTML('beforeend', "Error: Could not load welcome message.");
        chatContainer.appendChild(errorMessageDiv);
    }
}

// FUNCIÓN PARA LOCALIZAR EL MENSAJE BOT MÁS RECIENTE
function getLastBotMessageContent() {
    const elements = document.querySelectorAll('.bot-message-content');
    return elements.length > 0 ? elements[elements.length - 1] : null;
}

// EVENTO AL MODIFICAR EL TAMAÑO DEL NAVEGADOR
window.addEventListener('resize', function () {
    const lastDiv = getLastBotMessageContent();
    if (lastDiv && tempImageUrls.length>0) {
        callbacks_functions.generateImageCarrousel(lastDiv, tempImageUrls);
    }
});

// ARRANCAR EL CHATBOT
async function initiateSession() {
    await startSession()
    await fetchWelcomeMessage(); // Cargar y mostrar el mensaje de bienvenida
}


// CARGA DE LA WEB
document.addEventListener("DOMContentLoaded", () => {
    initiateSession(); // Inicia la sesión

    // Selecciona el botón y el input
    const sendButton = document.querySelector("#send-button");
    const userInput = document.querySelector("#user-input");

    // Agrega evento de click para enviar el mensaje
    sendButton.addEventListener("click", () => {
        sendUserMessage(userInput.value);
    });

    // También permitir enviar el mensaje al presionar "Enter"
    userInput.addEventListener("keypress", (event) => {
        if (event.key === "Enter") {
            sendUserMessage(userInput.value);
        }
    });
});