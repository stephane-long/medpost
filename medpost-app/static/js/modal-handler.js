document.addEventListener('DOMContentLoaded', () => {
    const selectedFeed = document.querySelector('.row').getAttribute('data-selectedfeed'); // Get selectedfeed from data attribute
    const newspaper = document.querySelector('.row').getAttribute('data-newspaper'); // Get newspaper from data attribute
    const modifiedImages = {};
    
    document.querySelectorAll('[id^="newpost"]').forEach(modalElement => {
        const modalId = modalElement.id.replace('newpost', ''); // récupère l'id
        const container = document.getElementById(`dynamic-forms-container${modalId}`);
        const checkboxes = document.querySelectorAll(`#newpost${modalId} .network-checkbox`);
        const programmerButton = document.getElementById(`programmer-btn-${modalId}`);

        // Retrieve default values from data-* attributes
        const articleTitle = modalElement.getAttribute('data-title');
        const articleDescription = modalElement.getAttribute('data-description');
        const articleLink = modalElement.getAttribute('data-link');
        // const articleDatetime = modalElement.getAttribute('data-datetime');
        const minDatetime = modalElement.getAttribute('data-min-datetime');
        const articleImageUrl = modalElement.getAttribute('data-image-url');

        // Sauvegarde des formulaires pour chaque réseau sélectionné
        const saveFormData = (container) => {
            const formData = {};
            container.querySelectorAll('form').forEach(form => {
                const network = form.querySelector('input[name="network"]').value;
                formData[network] = {};
                form.querySelectorAll('textarea, input').forEach(field => {
                    if (field.name) {
                        formData[network][field.name] = field.value;
                    }
                });
                console.log(formData[network]);
            });
            return formData;
        };

        // Réinitialisation des formulaires lors de l'ouverture de modale
        let isModalInitialized = false;
        modalElement.addEventListener('shown.bs.modal', () => {
            if (!isModalInitialized) {
                regenerateForms(); 
                isModalInitialized = true;
            }
        });

        // Restauration des formulaires
        const restoreFormData = (container, formData) => {
            container.querySelectorAll('form').forEach(form => {
                const network = form.querySelector('input[name="network"]').value;
                if (formData[network]) {
                    form.querySelectorAll('textarea, input').forEach(field => {
                        if (field.name && formData[network][field.name] !== undefined) {
                            field.value = formData[network][field.name];
                        }
                    });
                }
            });
        };

        const regenerateForms = () => {
            // articleImageUrl : url originale de l'image
            // id="imageUrlInput_${network}" : URL de l'image à passer à /newpost
            // modifiedImages[modalId]?.[network] : URL de l'image à afficher
            const existingFormData = saveFormData(container);
            container.innerHTML = '';
            checkboxes.forEach(checkbox => {
                if (checkbox.checked) {
                    const network = checkbox.value;
                    const formId = `form-${network}-${modalId}`;
                    const form = document.createElement('div');
                    form.id = formId;
                    form.className = 'card mb-3';
                    form.innerHTML = `
                        <div class="card-header text-white bg-${network === 'X' ? 'dark' : network === 'Bluesky' ? 'info' : 'primary'}">
                            <strong>${network}</strong>
                        </div>
                        <div class="card-body">
                            <form action="/new_post" method="post" enctype="multipart/form-data">
                                <input type="hidden" name="article_id" value="${modalId}">
                                <input type="hidden" name="network" value="${network}">
                                <input type="hidden" name="selectedfeed" value="${selectedFeed}">
                                <input type="hidden" name="newspaper" value="${newspaper}">
                                <input type="hidden" name="description" value="${articleDescription}">
                                <input type="hidden" name="image_url" value="${articleImageUrl}">
                                    ${
                                        network === 'X'
                                        ? `
                                        <div class="row">
                                            <div class="col-8 border rounded p-2">
                                                <label for="title_${network}_${modalId}" class="form-label fw-bold">Titre du post</label>
                                                <textarea class="form-control" id="title_${network}_${modalId}" name="title" rows="2" required>${articleTitle}</textarea>                                                
                                                <div class="position-relative">
                                                    <img id="previewImage_${network}_${modalId}" src="${modifiedImages[modalId]?.[network]?.url || articleImageUrl}" class="w-100 mt-3 d-block rounded-3" alt=""/>
                                                    <div id="caption_${network}_${modalId}" class="legend position-absolute start-50 translate-middle-x rounded bg-dark bg-opacity-75 text-white py-1 px-2 text-truncate">
                                                        ${articleTitle}
                                                    </div>
                                                    <a href="${articleLink}" class="card-link" target="_blank">De lequotidiendumedecin.fr</a>
                                                </div>
                                            </div>
                                            <div class="col-4">
                                                <label for="date_${network}_${modalId}" class="form-label fw-bold">Date et heure</label>
                                                <input type="datetime-local" class="form-control mb-3" id="date_${network}_${modalId}" name="datetime" value="${minDatetime}" min="${minDatetime}" style="width: 250px;" required>
                                                <label for="modifyImageFormFile_${network}_${modalId}" class="form-label fw-bold">Modifier l'image</label>
                                                <input type="file" class="form-control mb-3" id="modifyImageFormFile_${network}_${modalId}" accept="image/*">
                                                <button type="button" class="btn btn-primary" id="modifyImageBtn_${network}_${modalId}">Upload</button>
                                            </div>
                                        </div>
                                        `
                                        : `
                                        <input type="hidden" id="imageUrlInput_${network}" name="image_url" value="${articleImageUrl}">
                                        <input type="hidden" name="title" value="${articleTitle}">
                                        <div class="row">
                                            <div class="col-8 border rounded p-2">
                                                <label for="tagline_${network}_${modalId}" class="form-label fw-bold">Accroche du post</label>
                                                <textarea class="form-control" id="tagline_${network}_${modalId}" name="tagline" rows="2" required></textarea>
                                                <img id="previewImage_${network}_${modalId}" src="${modifiedImages[modalId]?.[network]?.url || articleImageUrl}" class="w-100 mt-3 rounded mb-2" alt=""/>
                                                <div class="legend-title">${articleTitle}</div>
                                                <div class="legend-chapo">${articleDescription.length > 165 ? articleDescription.substring(0, 165) + '...' : articleDescription}</div>
                                                <a href="${articleLink}" class="card-link" target="_blank">@ www.lequotidiendumedecin.fr</a>
                                            </div>
                                            <div class="col-4">
                                                <label for="date_${network}_${modalId}" class="form-label fw-bold">Date et heure</label>
                                                <input type="datetime-local" class="form-control" id="date_${network}_${modalId}" name="datetime" value="${minDatetime}" min="${minDatetime}" style="width: 250px;" required>
                                                <label for="modifyImageFormFile_${network}_${modalId}" class="form-label fw-bold">Modifier l'image</label>
                                                <input type="file" class="form-control mb-3" id="modifyImageFormFile_${network}_${modalId}" accept="image/*">
                                                <button type="button" class="btn btn-primary" id="modifyImageBtn_${network}_${modalId}">Upload</button>

                                            </div>
                                        </div>
                                        `
                                    }
                            </form>
                        </div>
                    `;
                    container.appendChild(form);

                    // Upload d'un fichier image
                    const uploadImageBtn = document.getElementById(`modifyImageBtn_${network}_${modalId}`);
                    const fileInputForm = document.getElementById(`modifyImageFormFile_${network}_${modalId}`);
                    const previewImageElement = document.getElementById(`previewImage_${network}_${modalId}`);
                    // const imageUrlInput = document.getElementById(`imageUrlInput_${network}`);
                    uploadImageBtn.disabled = true;

                    // Activation du bouton upload si nom de fichier fourni
                    fileInputForm.addEventListener('change', () => {
                        if (fileInputForm.files.length > 0) {
                            uploadImageBtn.disabled = false;
                        } else {
                            uploadImageBtn.disabled = true;
                        }
                    });

                    // Mise à jour de l'image
                    uploadImageBtn.addEventListener('click', () => {
                        const imageFile = fileInputForm.files[0];
                        if (imageFile) {
                            const reader = new FileReader();
                            reader.onload = (event) => {
                                const urlData = event.target.result; // URL de données
                                previewImageElement.src = urlData;
                                // Stocker le chemin de l'image modifiée
                                if (!modifiedImages[modalId]) {
                                    modifiedImages[modalId] = {};
                                };
                                modifiedImages[modalId][network] = {
                                    file: imageFile,
                                    url: urlData
                                    
                                };
                            };                  
                            reader.readAsDataURL(imageFile);
                        }
                    });

                    // Gestion des légendes des photos
                    /* if (network === 'X') {
                        const titleField = document.getElementById(`title_${network}_${modalId}`);
                        const caption = document.getElementById(`caption_${network}_${modalId}`);
                        titleField.addEventListener('input', () => {
                            caption.textContent = titleField.value;
                        })
                    } */
                }
            });
            restoreFormData(container, existingFormData);
        };

        // Regénération des formulaires en cas de checkbox cochée
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                regenerateForms();
            });
        });
        if (programmerButton) { // Add null check for programmerButton
            programmerButton.addEventListener('click', () => {
                const forms = container.querySelectorAll('form');
                let allValid = true; // Flag to check if all forms are valid

                forms.forEach(form => {
                    // Check if the form is valid
                    if (!form.checkValidity()) {
                        allValid = false;

                        // Highlight invalid fields
                        form.querySelectorAll(':invalid').forEach(field => {
                            field.classList.add('is-invalid');

                            // Remove highlight when the user starts typing
                            field.addEventListener('input', () => {
                                field.classList.remove('is-invalid');
                            });
                        });
                    }
                });

                if (allValid) {
                    // Submit all valid forms
                    const promises = [];
                    forms.forEach(form => {
                        const formData = new FormData(form);
                        const network = form.querySelector('input[name="network"]').value;
                        // Ajouter le fichier image au FormData
                        // const fileInput = form.querySelector('input[type="file"]');
                        if (modifiedImages[modalId] && modifiedImages[modalId][network]) {
                            const imageFile = modifiedImages[modalId][network].file;
                            // formData.append('imageFile', fileInput.files[0]); // Ajout du fichier image
                            formData.append('imageFile', imageFile);
                        }
                        const promise = fetch(form.action, {
                            method: form.method,
                            body: formData,
                        });
                        promises.push(promise);
                    });

                    // Wait for all form submissions to complete
                    Promise.all(promises)
                        .then(responses => {
                            const allSuccessful = responses.every(response => response.ok);
                            if (allSuccessful) {
                                // Redirect to the home route
                                window.location.href = `/?selectedfeed=${selectedFeed}&newspaper=${newspaper}`;
                            } else {
                                console.error("One or more form submissions failed.");
                            }
                        })
                        .catch(error => {
                            console.error("Error during form submissions:", error);
                        });
                }
            });
        }

        // Regenerate forms when the modal is shown
        modalElement.addEventListener('shown.bs.modal', () => {
            regenerateForms();
        });
    });
});
