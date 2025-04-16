$(document).ready(function() {
    // Reset the form when the modal is shown
    $('#import_lien').on('shown.bs.modal', function() {
        $('#importLink')[0].reset(); // Reset all form fields
        $('#responseMessage').text(''); // Clear the response message
    });

    // Handle form submission
    $('#importLink').submit(function(event) {
        event.preventDefault();
        const newspaper = $(this).data('newspaper');
        const formData = {
            imported_link: $('#link').val(),
            newspaper: newspaper
        };

        $.ajax({
            type: 'POST',
            url: '/import',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                $('#responseMessage').text(response.message || 'Lien importé avec succès.');

                if (response.title && response.description && response.image_url && response.link) {
                    $('#import_lien').modal('hide');                    
                    
                    const modalId = 'newpost-imported';
                    const modalElement = $(`#${modalId}`);
                    
                    if (!modalElement.length) {
                        $('body').append(`
                            <div class="modal fade" id="${modalId}" tabindex="-1">
                                <div class="modal-dialog modal-xl">
                                    <div class="modal-content">
                                        <div class="modal-header">
                                            <h1 class="modal-title fs-5 fw-bold">Nouveau post</h1>
                                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                        </div>
                                        <div class="modal-body">
                                            <form id="postCreationForm">
                                                <!-- Network selection -->
                                                <div class="mb-3 d-flex align-items-center flex-wrap">
                                                    <label class="form-label me-3 fw-bold">Sélectionnez les réseaux</label>
                                                    <div class="form-check form-check-inline me-2">
                                                        <input class="form-check-input network-checkbox" type="checkbox" id="x_checkbox_modal_imported" value="X">
                                                        <label class="form-check-label" for="x_checkbox_modal_imported">X</label>
                                                    </div>
                                                    <div class="form-check form-check-inline me-2">
                                                        <input class="form-check-input network-checkbox" type="checkbox" id="bluesky_checkbox_modal_imported" value="Bluesky">
                                                        <label class="form-check-label" for="bluesky_checkbox_modal_imported">Bluesky</label>
                                                    </div>
                                                    <div class="form-check form-check-inline">
                                                        <input class="form-check-input network-checkbox" type="checkbox" id="linkedin_checkbox_modal_imported" value="LinkedIn">
                                                        <label class="form-check-label" for="linkedin_checkbox_modal_imported">LinkedIn</label>
                                                    </div>
                                                </div>
                                                <!-- Dynamic forms container -->
                                                <div id="dynamic-forms-container-imported"></div>
                                            </form>
                                        </div>
                                        <div class="modal-footer">
                                            <button type="button" class="btn btn-primary" id="programmer-btn-imported">Créer le post</button>
                                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `);
                    }

                    // Fill the modal fields with the response data
                    $('#postTitle').val(response.title);
                    $('#postDescription').val(response.description);
                    $('#postImageUrl').val(response.image_url);
                    $('#postLink').val(response.link);

                    // Handle dynamic form generation based on selected networks
                    const container = $('#dynamic-forms-container-imported');
                    const checkboxes = $('.network-checkbox');
                    const programmerButton = $('#programmer-btn-imported');

                    const regenerateForms = () => {
                        container.html(''); // Clear existing forms
                        checkboxes.each(function() {
                            if ($(this).is(':checked')) {
                                const network = $(this).val();
                                const formId = `form-${network}-imported`;
                                const form = `
                                    <div class="card mb-3" id="${formId}">
                                        <div class="card-header text-white bg-${network === 'X' ? 'dark' : network === 'Bluesky' ? 'info' : 'primary'}">
                                            <strong>${network}</strong>
                                        </div>
                                        <div class="card-body">
                                            <input type="hidden" name="network" value="${network}">
                                            <div class="mb-3">
                                                <label for="title_${network}_imported" class="form-label fw-bold">Titre</label>
                                                <textarea class="form-control" id="title_${network}_imported" name="title" rows="3" required>${response.title}</textarea>
                                            </div>
                                            <div class="mb-3">
                                                <label for="description_${network}_imported" class="form-label fw-bold">Description</label>
                                                <textarea class="form-control" id="description_${network}_imported" name="description" rows="3" required>${response.description}</textarea>
                                            </div>
                                            <div class="mb-3">
                                                <label for="link_${network}_imported" class="form-label fw-bold">Lien</label>
                                                <input type="text" class="form-control" id="link_${network}_imported" name="link" value="${response.link}" required>
                                            </div>
                                        </div>
                                    </div>
                                `;
                                container.append(form);
                            }
                        });
                    };

                    // Regenerate forms when checkboxes are toggled
                    checkboxes.on('change', regenerateForms);

                    // Handle form submission
                    programmerButton.on('click', function() {
                        const forms = container.find('form');
                        let allValid = true;

                        forms.each(function() {
                            if (!this.checkValidity()) {
                                allValid = false;
                                $(this).find(':invalid').addClass('is-invalid');
                            }
                        });

                        if (allValid) {
                            forms.each(function() {
                                const formData = new FormData(this);
                                fetch('/new_post', {
                                    method: 'POST',
                                    body: formData,
                                }).then(response => {
                                    if (!response.ok) {
                                        console.error('Erreur lors de la création du post.');
                                    }
                                });
                            });

                            // Close the modal after submission
                            $(`#${modalId}`).modal('hide');
                        }
                    });

                    // Show the modal
                    $(`#${modalId}`).modal('show');
                }
            },
            error: function(error) {
                $('#responseMessage').text('Erreur lors du traitement des données.');
            }
        });
    });
});