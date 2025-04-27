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

        const regenerateForms = () => {
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
                                <!-- <div class="input-group input-group-lg"> -->
                                    ${
                                        network === 'X'
                                        ? `
                                        <div class="mb-3 ">
                                            <label for="title_${network}_${modalId}" class="form-label fw-bold">Titre du post</label>
                                            <textarea class="form-control" id="title_${network}_${modalId}" name="title" rows="1" required>${articleTitle}</textarea>
                                        </div>
                                        <div class="position-relative w-100 mb-3">
                                            <img src="${articleImageUrl}" class="w-50 d-block mx-auto rounded-3 mb-3" alt=""/>
                                            <div id="caption_${network}_${modalId}" class="legend position-absolute w-50 start-50 translate-middle-x rounded bg-dark bg-opacity-75 text-white py-1 px-2 text-truncate">
                                                ${articleTitle}
                                            </div>
                                        </div>
                                        `
                                        : `
                                        <div class="border rounded p-2 mb-3">
                                            <img src="${articleImageUrl}" class="img-fluid rounded mb-2" alt="Aperçu de l'image"/>
                                            <div class="mb-0">
                                                <label for="tagline_${network}_${modalId}" class="form-label fw-bold">Accroche du post</label>
                                                <textarea class="form-control" id="tagline_${network}_${modalId}" name="tagline" rows="2" required></textarea>
                                            </div>
                                        </div>
                                        `
                                    }
                                <!-- </div> -->
                            </form>
                        </div>
                    `;
                    container.appendChild(form);
           
                    // Gestion des légendes des photos
                    if (network === 'X') {
                        const titleField = document.getElementById(`title_${network}_${modalId}`);
                        const caption = document.getElementById(`caption_${network}_${modalId}`);
                        titleField.addEventListener('input', () => {
                            caption.textContent = titleField.value;
                        })
                    }
                }
            });
        };

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
