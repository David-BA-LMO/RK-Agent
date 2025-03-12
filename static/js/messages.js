// ESTRUCTURA DEL CONTENEDOR DEL MENSAJE DEL USUARIO
export function createUserMessageContainer(messageContent) {
    // Crear el div del mensaje del usuario
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", "user"); // Añadir las clases "message" y "user"

    // Crear el nodo de texto para el mensaje del usuario
    const textNode = document.createTextNode(messageContent);

    // Añadir el texto al contenedor del mensaje
    messageDiv.appendChild(textNode);

    document.getElementById("chat-container").appendChild(messageDiv);
}

// ESTRUCTURA DEL CONTENEDOR DEL MENSAJE DEL BOT
export function createBotMessageContainer() {
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", "bot");

    // Crear el contenedor del logo
    const logoContainer = document.createElement("div");
    logoContainer.classList.add("bot-logo-container");

    // Crear la imagen del logo
    const logo = document.createElement("img");
    logo.src = "static/images/bot-logo.png";
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

