import { createUserMessageContainer, createBotMessageContainer } from './messages.js';


// --------------------- CALLBACKS ---------------------
const callbacks_functions = {
    // INICIAR ANIMACIÓN DE CARGA AL REALIZAR BÚSQUEDA EN BASE DE DATOS. ESTAS FUNCIONES NO FUNCIONAN DADO QUE SE ESPERA QUE RECIBAN POR PARÁMETRO EL ELEMENTO PADRE DENTRO DE LA CUAL SE INSERTAN.
    handleLoadingDbStart: function (targetDiv) {
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

        targetDiv.appendChild(div);
    },

    // DETENER ANIMACIÓN DE CARGA AL REALIZAR BÚSQUEDA EN BASE DE DATOS
    handleLoadingDbEnd: function () {
        // Eliminar el div de animación de carga
        const div = document.getElementById('loading-div');
        if (div) {
            div.remove();
        }
    },

    // GENERACIÓN DEL CARRUSEL DE IMAGENES
    generateImageCarrousel: async function (targetDiv, tempImageUrls){
        console.log("Se ha generado un carrusel")
    
        // Crear el contenedor principal del carrusel
        const carouselContainer = document.createElement('div');
        carouselContainer.classList.add('carousel-container'); // Aplicar la clase CSS
        
        // Ajustar la altura del contenedor al 50% de su ancho
        const carouselHeight = Math.round(targetDiv.offsetWidth * 0.5); // 50% del ancho del contenedor padre
        carouselContainer.style.height = `${carouselHeight}px`;
    
        // Crear la pista de imágenes
        const imageTrack = document.createElement('div');
        imageTrack.classList.add('image-track'); // Aplicar la clase CSS
        imageTrack.style.width = `${tempImageUrls.length * targetDiv.offsetWidth}px`; // Ancho proporcional al número de imágenes
    
        // Transformar y añadir imágenes al carrusel
        const carouselWidth = targetDiv.offsetWidth;
        for (const url of tempImageUrls) {
            console.log(url);
            const img = document.createElement('img');
    
            // Esperar a que la imagen sea transformada
            const transformedImage = await transformImages(url, carouselWidth, carouselHeight);
    
            img.src = transformedImage; // Usar la imagen transformada
            imageTrack.appendChild(img);
        }
    
        // Añadir la pista de imágenes al contenedor del carrusel
        carouselContainer.appendChild(imageTrack);
    
        // Crear controles de navegación
        let currentIndex = 0;
    
        const prevButton = document.createElement('button');
        prevButton.type = 'button';
        prevButton.textContent = '<';
        prevButton.classList.add('carousel-button', 'carousel-button--prev'); // Clases CSS para diseño
        prevButton.addEventListener('click', () => {
            if (currentIndex > 0) {
                currentIndex--;
                console.log(currentIndex);
                const offset = currentIndex * -carouselWidth;
                imageTrack.style.transform = `translateX(${offset}px)`; // Mover la pista hacia la derecha
            }
        });
        console.log("BOTON ANTERIOR ASIGNADO");
    
        const nextButton = document.createElement('button');
        nextButton.type = 'button';
        nextButton.textContent = '>';
        nextButton.classList.add('carousel-button', 'carousel-button--next'); // Clases CSS para diseño
        nextButton.addEventListener('click', () => {
                currentIndex++;
                console.log(currentIndex);
                const offset = currentIndex * -carouselWidth;
                imageTrack.style.transform = `translateX(${offset}px)`; // Mover la pista hacia la izquierda
        });
        console.log("BOTON SIGUIENTE ASIGNADO");
    
        // Añadir controles al contenedor del carrusel
        carouselContainer.appendChild(prevButton);
        carouselContainer.appendChild(nextButton);
    
        // Añadir el carrusel al contenedor objetivo
        targetDiv.appendChild(carouselContainer);
    
        // Reiniciar tempImageUrls
        tempImageUrls = [];
    },    

    // GENERAR EL FORMULARIO DE RESERVA DE VISITAS
    generateBookForm: function (targetDiv, input) {
        console.log("FORMULARIO...");
        if (!targetDiv) {
            console.error("targetDiv no encontrado.");
            return;
        }
    
        // Crear el formulario
        const form = document.createElement('form');
        form.classList.add('book-form');
    
        // Campo de nombre
        const nameLabel = document.createElement('label');
        nameLabel.textContent = 'Nombre y Apellidos:';
        nameLabel.setAttribute('for', 'nombre');
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.name = 'nombre';
        nameInput.id = 'nombre';
        nameInput.required = true;
        nameInput.pattern = '[A-Za-zÁÉÍÓÚáéíóúÑñ ]+';
        nameInput.placeholder = 'Ingrese su nombre completo';
    
        // Campo de número de teléfono
        const phoneLabel = document.createElement('label');
        phoneLabel.textContent = 'Número de Teléfono:';
        phoneLabel.setAttribute('for', 'telefono');
        const phoneInput = document.createElement('input');
        phoneInput.type = 'tel';
        phoneInput.name = 'telefono';
        phoneInput.id = 'telefono';
        phoneInput.required = true;
        phoneInput.pattern = '[0-9]{9}';
        phoneInput.placeholder = 'Ingrese su número de teléfono';
    
        // Campo de correo electrónico
        const emailLabel = document.createElement('label');
        emailLabel.textContent = 'Correo Electrónico:';
        emailLabel.setAttribute('for', 'correo');
        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.name = 'correo';
        emailInput.id = 'correo';
        emailInput.required = true;
        emailInput.placeholder = 'Ingrese su correo electrónico';
    
        // Botón de envío
        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.textContent = 'Enviar';
        submitButton.classList.add('submit-button');
    
        // Manejar evento de envío
        form.addEventListener('submit', function (event) {
            event.preventDefault(); // Evitar recarga de página
    
            // Crear objeto con datos del formulario y pasar nombre y correo a minúsculas
            const datos_form_dict = {
                username: nameInput.value.trim().toLowerCase(),
                phone: phoneInput.value.trim(),
                email: emailInput.value.trim().toLowerCase(),
                action: input
            };
    
            // Enviar datos a /submit-form
            fetch('/submit-form', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(datos_form_dict)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    createUserMessageContainer("Ubicación registrada");
                    // Eliminar solo el formulario una vez se hayan enviado los datos
                    form.remove();
                } else {
                    alert('Error al enviar el formulario. Inténtelo de nuevo.');
                }
            })
            .catch(error => {
                console.error('Error en la solicitud:', error);
            });
        });
    
        // Agregar los elementos al formulario
        form.appendChild(nameLabel);
        form.appendChild(nameInput);
        form.appendChild(phoneLabel);
        form.appendChild(phoneInput);
        form.appendChild(emailLabel);
        form.appendChild(emailInput);
        form.appendChild(submitButton);
    
        // Agregar el formulario al targetDiv
        targetDiv.appendChild(form);
    },

    // CONFIRMACIÓN PARA COMPARTIR DATOS
    generateConfirmationPopup: function (targetDiv, input) {
        return new Promise((resolve) => {
            if (!targetDiv) {
                console.error("targetDiv no encontrado.");
                resolve(null);
                return;
            }
    
            // Crear el contenedor del mensaje dentro del targetDiv
            const popupContainer = document.createElement('div');
            popupContainer.style.width = '100%';
            popupContainer.style.maxWidth = '500px';
            popupContainer.style.margin = '20px auto';
            popupContainer.style.border = '1px solid #ddd';
            popupContainer.style.borderRadius = '10px';
            popupContainer.style.padding = '15px';
            popupContainer.style.backgroundColor = '#f9f9f9';
            popupContainer.style.boxShadow = '0px 2px 4px rgba(0, 0, 0, 0.1)';
            popupContainer.style.textAlign = 'center';
    
            // Crear el mensaje
            const message = document.createElement('p');
            message.textContent = 'RK Iglesias desea que comparta con nosotros ciertos datos, con el solo fin de ofrecerle un servicio más personalizado. Este paso es necesario para realizar gestiones como la organización de visitas.';
            message.style.marginBottom = '10px';
    
            // Crear el enlace a la política de privacidad
            const privacyLink = document.createElement('a');
            privacyLink.href = 'https://www.agenciaiglesias.com/politica-de-privacidad/';
            privacyLink.textContent = 'Política de Tratamiento de Datos';
            privacyLink.target = '_blank';
            privacyLink.style.display = 'block';
            privacyLink.style.marginBottom = '15px';
            privacyLink.style.color = '#007bff';
            privacyLink.style.textDecoration = 'none';
    
            // Contenedor de los botones
            const buttonContainer = document.createElement('div');
            buttonContainer.style.display = 'flex';
            buttonContainer.style.justifyContent = 'center';
            buttonContainer.style.gap = '15px';
    
            // Botón Confirmar
            const confirmButton = document.createElement('button');
            confirmButton.textContent = 'Confirmar';
            confirmButton.style.padding = '10px 20px';
            confirmButton.style.backgroundColor = '#28a745';
            confirmButton.style.color = 'white';
            confirmButton.style.border = 'none';
            confirmButton.style.borderRadius = '5px';
            confirmButton.style.cursor = 'pointer';
    
            // Botón Rechazar
            const rejectButton = document.createElement('button');
            rejectButton.textContent = 'Rechazar';
            rejectButton.style.padding = '10px 20px';
            rejectButton.style.backgroundColor = '#dc3545';
            rejectButton.style.color = 'white';
            rejectButton.style.border = 'none';
            rejectButton.style.borderRadius = '5px';
            rejectButton.style.cursor = 'pointer';

             // Agregar elementos al popupContainer
             buttonContainer.appendChild(confirmButton);
             buttonContainer.appendChild(rejectButton);
             popupContainer.appendChild(message);
             popupContainer.appendChild(privacyLink);
             popupContainer.appendChild(buttonContainer);
     
             // Insertar el marco dentro del targetDiv
             targetDiv.appendChild(popupContainer);
    
            // Función para enviar la decisión a /confirm-data
            function sendConfirmationResponse(accepted) {
                console.log("ENVIANDO RESPUESTA...");
                fetch('/confirm-data', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ accepted: accepted })  // true si aceptó, false si rechazó
                })
                .then(response => response.json())
                .then(data => console.log("Respuesta del servidor:", data))
                .catch(error => console.error("Error en la solicitud:", error));
            }
    
            // Eventos de los botones
            confirmButton.addEventListener('click', () => {
                console.log("GENERANDO EL FORMULARIO...");
                sendConfirmationResponse(true);  // Enviar confirmación
                popupContainer.remove(); // Eliminar el marco
                callbacks_functions.generateBookForm(targetDiv, input);  // Ejecuta la función que genera el formulario
                
                resolve(null);       
                ///resolve({ type: "function", content: "generateBookForm", input: input});
            });
    
            rejectButton.addEventListener('click', () => {
                sendConfirmationResponse(false);  // Enviar rechazo
                popupContainer.remove();          // Eliminar el marco
                resolve(null);
            });

        });
    },

    generateMapLocalization: function (targetDiv, city_localization) {
        return new Promise((resolve, reject) => {
            // Asegurar que Leaflet está disponible
            if (typeof L === 'undefined') {
                console.error('Leaflet library is required but not loaded.');
                reject('Leaflet library not loaded');
                return;
            }
    
            // Crear un título para el mapa
            const title = document.createElement('h3');
            title.textContent = "Indica la localización aproximada donde te interese encontrar un inmueble";
            title.style.textAlign = 'center';
            title.style.marginBottom = '10px';
            targetDiv.appendChild(title);
    
            // Crear un contenedor para el mapa
            const mapContainer = document.createElement('div');
            mapContainer.style.width = '100%';
            mapContainer.style.height = '400px';
            mapContainer.style.marginTop = '10px';
            targetDiv.appendChild(mapContainer);
    
            // Crear el mapa centrado en la localización proporcionada
            const map = L.map(mapContainer).setView(city_localization, 13);
    
            // Agregar capa de mapa base desde OpenStreetMap
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(map);
    
            let selectedMarker = null;
            let selectedCoords = null;
            let selectedCircle = null;
    
            // Evento de clic en el mapa para seleccionar una ubicación
            map.on('click', function (event) {
                if (selectedMarker) {
                    map.removeLayer(selectedMarker);
                }
                if (selectedCircle) {
                    map.removeLayer(selectedCircle);
                }
    
                selectedCoords = event.latlng;
                selectedMarker = L.marker(selectedCoords).addTo(map);
    
                // Agregar círculo con animación
                let radius = 0;
                selectedCircle = L.circle(selectedCoords, {
                    color: 'yellow',
                    fillColor: 'yellow',
                    fillOpacity: 0.3,
                    radius: radius
                }).addTo(map);
    
                // Animación del círculo
                const interval = setInterval(() => {
                    if (radius >= 1000) {
                        clearInterval(interval);
                    } else {
                        radius += 50;
                        selectedCircle.setRadius(radius);
                    }
                }, 50);
            });
    
            // Crear un botón de confirmación
            const confirmButton = document.createElement('button');
            confirmButton.textContent = 'Confirmar Ubicación';
            confirmButton.style.position = 'absolute';
            confirmButton.style.bottom = '10px';
            confirmButton.style.left = '50%';
            confirmButton.style.transform = 'translateX(-50%)';
            confirmButton.style.padding = '10px 20px';
            confirmButton.style.backgroundColor = '#007bff';
            confirmButton.style.color = 'white';
            confirmButton.style.border = 'none';
            confirmButton.style.borderRadius = '5px';
            confirmButton.style.cursor = 'pointer';
            confirmButton.style.zIndex = '1000';
    
            targetDiv.style.position = 'relative';
            targetDiv.appendChild(confirmButton);
    
            // Evento de clic en el botón para enviar las coordenadas seleccionadas
            confirmButton.addEventListener('click', function () {
                if (!selectedCoords) {
                    alert('Por favor selecciona una ubicación en el mapa.');
                    return;
                }
    
                const requestData = {
                    type: "inm_localization_action",
                    content: [selectedCoords.lat, selectedCoords.lng]
                };
    
                // Limpiar el mapa y resolver la promesa con los datos
                mapContainer.remove();
                title.remove();
                confirmButton.remove();
                createUserMessageContainer("Ubicación registrada")
    
                resolve(requestData);
            });
        });
    },

    // PRESENTACIÓN GENÉRICA DE INMUEBLES
    generalPresentation: function (targetDiv, inmuebles) {
        // Crear el contenedor de fichas
        const container = document.createElement("div");
        container.style.display = "grid";
        container.style.gridTemplateColumns = "repeat(2, 1fr)"; // Dos columnas
        container.style.gap = "20px";
        container.style.padding = "20px";
        container.style.maxWidth = "800px";
        container.style.margin = "0 auto";
    
        // Limitar a 4 inmuebles máximo
        const inmueblesMostrar = inmuebles.slice(0, 4);
    
        inmueblesMostrar.forEach(inmueble => {
            const { data_inm, url, url_media } = inmueble;
    
            // Verificar que data_inm existe y proporcionar valores predeterminados
            const Barrio = data_inm?.Barrio ?? "Desconocido";
            const Numero = data_inm?.Numero ?? 0;
            const NumAseos = data_inm?.NumAseos ?? 0;
            const Poblacion = data_inm?.Poblacion ?? "Desconocida";
            const Provincia = data_inm?.Provincia ?? "Desconocida";
            const Direccion = data_inm?.Direccion ?? "Dirección no disponible";
            const NumDormitorios = data_inm?.NumDormitorios ?? 0;
            const Precio = data_inm?.Precio ?? 0;
            const Superficie = data_inm?.Superficie ?? "N/A";
    
            // Crear la ficha
            const card = document.createElement("div");
            card.style.border = "1px solid #ddd";
            card.style.borderRadius = "10px";
            card.style.boxShadow = "0 4px 8px rgba(0,0,0,0.1)";
            card.style.overflow = "hidden";
            card.style.backgroundColor = "#fff";
            card.style.display = "flex";
            card.style.flexDirection = "column";
            card.style.alignItems = "center";
            card.style.padding = "15px";
            card.style.cursor = "pointer"; // Indicar que la tarjeta es clickeable
            card.style.transition = "0.3s";
            card.onmouseover = () => (card.style.boxShadow = "0 6px 12px rgba(0,0,0,0.2)");
            card.onmouseleave = () => (card.style.boxShadow = "0 4px 8px rgba(0,0,0,0.1)");
    
            // Hacer que la ficha abra la URL en una nueva ventana al hacer clic
            card.onclick = () => {
                if (url) {
                    window.open(url, "_blank");
                }
            };
    
            // Imagen principal
            const image = document.createElement("img");
            image.src = url_media || "/static/images/rk-logo-extended.png"; // Imagen de respaldo si no hay foto
            image.style.width = "100%";
            image.style.height = "180px";
            image.style.objectFit = "cover";
            image.style.borderRadius = "8px";
            card.appendChild(image);
    
            // Contenedor de detalles
            const details = document.createElement("div");
            details.style.textAlign = "center";
            details.style.padding = "10px";
    
            // Dirección
            const title = document.createElement("h3");
            title.textContent = `${Barrio}, ${Direccion}, ${Numero}`;
            title.style.margin = "5px 0";
            title.style.fontSize = "14px";
            title.style.color = "#333";
            details.appendChild(title);
    
            // Ubicación
            const location = document.createElement("p");
            location.textContent = `${Poblacion}, ${Provincia}`;
            location.style.fontSize = "14px";
            location.style.color = "#777";
            details.appendChild(location);
    
            // Número de dormitorios
            const rooms = document.createElement("p");
            rooms.textContent = `🛏 ${NumDormitorios} | 🚽 ${NumAseos} | 📏 ${Superficie}m²`;
            rooms.style.fontSize = "14px";
            rooms.style.color = "#555";
            details.appendChild(rooms);
    
            // Precio (destacado)
            const price = document.createElement("p");
            price.textContent = `${new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(Precio)}`;
            price.style.fontSize = "18px";
            price.style.fontWeight = "bold";
            price.style.color = "#D32F2F"; // Rojo para destacar
            details.appendChild(price);
    
            card.appendChild(details);
            container.appendChild(card);
        });
    
        targetDiv.appendChild(container);
    }
};


// REESCALADO DE IMAGENES
async function transformImages(imageUrl, targetWidth, targetHeight) {
    const img = await loadImage(imageUrl);

    const canvas = document.createElement('canvas');
    canvas.width = targetWidth;
    canvas.height = targetHeight;
    const ctx = canvas.getContext('2d');

    // Rellenar con el fondo gris
    ctx.fillStyle = '#ccc';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Calcular las proporciones para mantener la relación de aspecto
    const imgAspect = img.width / img.height;
    const targetAspect = targetWidth / targetHeight;

    let drawWidth, drawHeight;
    if (imgAspect > targetAspect) {
        // La imagen es más ancha que el contenedor
        drawWidth = targetWidth;
        drawHeight = targetWidth / imgAspect;
    } else {
        // La imagen es más alta o igual que el contenedor
        drawHeight = targetHeight;
        drawWidth = targetHeight * imgAspect;
    }

    // Calcular el offset para centrar la imagen
    const offsetX = (targetWidth - drawWidth) / 2;
    const offsetY = (targetHeight - drawHeight) / 2;

    // Dibujar la imagen redimensionada y centrada
    ctx.drawImage(img, offsetX, offsetY, drawWidth, drawHeight);

    // Devolver la imagen transformada como Data URL
    return canvas.toDataURL('image/png');
}

function loadImage(url) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.crossOrigin = "anonymous"; // Habilitar CORS si es necesario
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = url;
    });
}

export default callbacks_functions;