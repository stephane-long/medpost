document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[id^="newpost"]').forEach(modalElement => {
        const modalId = modalElement.id.replace('newpost', '');
        const container = document.getElementById(`dynamic-forms-container${modalId}`);
        const checkboxes = document.querySelectorAll(`#newpost${modalId} .network-checkbox`);
        const programmerButton = document.getElementById(`programmer-btn-${modalId}`);

        // Retrieve default values from data-* attributes
        const articleTitle = modalElement.getAttribute('data-title');
        const articleDescription = modalElement.getAttribute('data-description');
        const articleTagline = modalElement.getAttribute('data-tagline');
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
                            <strong>Formulaire pour ${network}</strong>
                        </div>
                        <div class="card-body">
                            <form action="/new_post" method="post">
                                <input type="hidden" name="article_id" value="${modalId}">
                                <input type="hidden" name="network" value="${network}">
                                <div class="mb-3">
                                    <label for="title_${network}_${modalId}" class="form-label fw-bold">Titre du post (${network})</label>
                                    <textarea class="form-control" id="title_${network}_${modalId}" name="title" rows="3" required>${articleTitle}</textarea>
                                </div>
                                ${
                                    network !== 'X'
                                        ? `
                                        <div class="mb-3">
                                            <label for="description_${network}_${modalId}" class="form-label fw-bold">Description du post (${network})</label>
                                            <textarea class="form-control" id="description_${network}_${modalId}" name="description" rows="3" required>${articleDescription}</textarea>
                                        </div>
                                        <div class="mb-3">
                                            <label for="tagline_${network}_${modalId}" class="form-label fw-bold">Accroche du post (${network})</label>
                                            <textarea class="form-control" id="tagline_${network}_${modalId}" name="tagline" rows="3" required>${articleTagline}</textarea>
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
                                    <input type="datetime-local" class="form-control" id="date_${network}_${modalId}" name="datetime" value="${articleDatetime}" min="${minDatetime}" required>
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
                forms.forEach(form => {
                    const formData = new FormData(form);
                    fetch(form.action, {
                        method: form.method,
                        body: formData,
                    }).then(response => {
                        if (response.ok) {
                            console.log(`Form for network ${form.querySelector('input[name="network"]').value} submitted successfully.`);
                        } else {
                            console.error(`Error submitting form for network ${form.querySelector('input[name="network"]').value}.`);
                        }
                    }).catch(error => {
                        console.error('Error:', error);
                    });
                });

                // Close the modal programmatically
                const modalInstance = bootstrap.Modal.getInstance(modalElement);
                modalInstance.hide();
            });
        } else {
            console.warn(`Programmer button not found for modal ID: ${modalId}`);
        }

        // Regenerate forms when the modal is shown
        modalElement.addEventListener('shown.bs.modal', () => {
            regenerateForms();
        });
    });
});
