document.addEventListener('DOMContentLoaded', () => {
    const selectedFeed = document.querySelector('.row').getAttribute('data-selectedfeed'); // Get selectedfeed from data attribute
    const newspaper = document.querySelector('.row').getAttribute('data-newspaper'); // Get newspaper from data attribute
    
    document.querySelectorAll('[id^="newpost"]').forEach(modalElement => {
        const modalId = modalElement.id.replace('newpost', '');
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

        // Sauvegarde des formulaires
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
            });
            return formData;
        };

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
            const existingFormData = saveFormData(container);
            container.innerHTML = ''; // Clear existing forms
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
                            <form action="/new_post" method="post">
                                <input type="hidden" name="article_id" value="${modalId}">
                                <input type="hidden" name="network" value="${network}">
                                <input type="hidden" name="image_url" value="${articleImageUrl}">
                                <input type="hidden" name="description" value="${articleDescription}">
                                    ${
                                        network === 'X'
                                        ? `
                                        <div class="row">
                                            <div class="col-8 border rounded p-2">
                                                <label for="title_${network}_${modalId}" class="form-label fw-bold">Titre du post</label>
                                                <textarea class="form-control" id="title_${network}_${modalId}" name="title" rows="2" required>${articleTitle}</textarea>
                                                <div class="position-relative">
                                                    <img src="${articleImageUrl}" class="w-100 mt-3 d-block rounded-3" alt=""/>
                                                    <div id="caption_${network}_${modalId}" class="legend position-absolute start-50 translate-middle-x rounded bg-dark bg-opacity-75 text-white py-1 px-2 text-truncate">
                                                        ${articleTitle}
                                                    </div>
                                                    <a href="${articleLink}" class="card-link" target="_blank">De lequotidiendumedecin.fr</a>
                                                </div>
                                            </div>
                                            <div class="col-4">
                                                <label for="date_${network}_${modalId}" class="form-label fw-bold">Date et heure</label>
                                                <input type="datetime-local" class="form-control" id="date_${network}_${modalId}" name="datetime" value="${minDatetime}" min="${minDatetime}" style="width: 250px;" required>
                                            </div>
                                        </div>
                                        `
                                        : `
                                        <input type="hidden" name="title" value="${articleTitle}">
                                        <div class="row">
                                            <div class="col-8 border rounded p-2">
                                                <label for="tagline_${network}_${modalId}" class="form-label fw-bold">Accroche du post</label>
                                                <textarea class="form-control" id="tagline_${network}_${modalId}" name="tagline" rows="2" required></textarea>
                                                <img src="${articleImageUrl}" class="w-100 mt-3 rounded mb-2" alt=""/>
                                                <div class="legend-title">${articleTitle}</div>
                                                <div class="legend-chapo">${articleDescription.length > 165 ? articleDescription.substring(0, 165) + '...' : articleDescription}</div>
                                                <a href="${articleLink}" class="card-link" target="_blank">@ www.lequotidiendumedecin.fr</a>
                                            </div>
                                            <div class="col-4">
                                                <label for="date_${network}_${modalId}" class="form-label fw-bold">Date et heure</label>
                                                <input type="datetime-local" class="form-control" id="date_${network}_${modalId}" name="datetime" value="${minDatetime}" min="${minDatetime}" style="width: 250px;" required>
                                            </div>
                                        </div>
                                        `
                                    }
                            </form>
                        </div>
                    `;
                    container.appendChild(form);
           

                    // Gestion des légendes des photos 165
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

        let isModalInitialized = false;
        modalElement.addEventListener('shown.bs.modal', () => {
            if (!isModalInitialized) {
                regenerateForms(); // Réinitialiser uniquement lors de la première ouverture
                isModalInitialized = true;
            }
        });

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
