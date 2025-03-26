document.addEventListener('DOMContentLoaded', () => {
    const selectedFeed = document.querySelector('.row').getAttribute('data-selectedfeed') || 'qdm'; // Get selectedfeed from data attribute

    document.querySelectorAll('[id^="newpost"]').forEach(modalElement => {
        const modalId = modalElement.id.replace('newpost', '');
        const container = document.getElementById(`dynamic-forms-container${modalId}`);
        const checkboxes = document.querySelectorAll(`#newpost${modalId} .network-checkbox`);
        const programmerButton = document.getElementById(`programmer-btn-${modalId}`);

        // Retrieve default values from data-* attributes
        const articleTitle = modalElement.getAttribute('data-title');
        const articleDescription = modalElement.getAttribute('data-description');
        const articleLink = modalElement.getAttribute('data-link');
        const articleDatetime = modalElement.getAttribute('data-datetime');
        const minDatetime = modalElement.getAttribute('data-min-datetime'); // Retrieve minimum datetime

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
                        <div class="card-header text-white bg-${network === 'X' ? 'dark' : network === 'Bluesky' ? 'primary' : 'info'}">
                            <strong>${network}</strong>
                        </div>
                        <div class="card-body">
                            <form action="/new_post" method="post">
                                <input type="hidden" name="article_id" value="${modalId}">
                                <input type="hidden" name="network" value="${network}">
                                <div class="mb-3">
                                    <label for="title_${network}_${modalId}" class="form-label fw-bold">Titre du post</label>
                                    <textarea class="form-control" id="title_${network}_${modalId}" name="title" rows="3" required>${articleTitle}</textarea>
                                </div>
                                ${
                                    network !== 'X'
                                        ? `
                                        <div class="mb-3">
                                            <label for="description_${network}_${modalId}" class="form-label fw-bold">Description du post</label>
                                            <textarea class="form-control" id="description_${network}_${modalId}" name="description" rows="3" required>${articleDescription}</textarea>
                                        </div>
                                        <div class="mb-3">
                                            <label for="tagline_${network}_${modalId}" class="form-label fw-bold">Accroche du post</label>
                                            <textarea class="form-control" id="tagline_${network}_${modalId}" name="tagline" rows="3" required></textarea>
                                        </div>
                                        `
                                        : ''
                                }
                                <div class="mb-3">
                                    <label for="link_${network}_${modalId}" class="form-label fw-bold">URL</label>
                                    <input type="text" class="form-control" id="link_${network}_${modalId}" name="link" value="${articleLink}">
                                </div>
                                <div class="mb-3">
                                    <label for="date_${network}_${modalId}" class="form-label fw-bold">Date et heure</label>
                                    <input type="datetime-local" class="form-control" id="date_${network}_${modalId}" name="datetime" value="${articleDatetime}" min="${minDatetime}" style="width: 250px;" required>
                                </div>
                            </form>
                        </div>
                    `;
                    container.appendChild(form);
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
                const promises = []; // Collect promises for all form submissions

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
                            // Redirect to the home route with the selectedfeed parameter
                            window.location.href = `/?selectedfeed=${selectedFeed}`;
                        } else {
                            console.error("One or more form submissions failed.");
                        }
                    })
                    .catch(error => {
                        console.error("Error during form submissions:", error);
                    });
            });
        }

        // Regenerate forms when the modal is shown
        modalElement.addEventListener('shown.bs.modal', () => {
            regenerateForms();
        });
    });
});
