document.addEventListener('DOMContentLoaded', () => {
    const imageModal = document.getElementById('importImage');
    const importFileForm = document.getElementById('importFileForm');
    const networkFormImage = document.getElementById('networkForm_image');
    const postImageFormContainer = document.getElementById('postImageFormContainer');
    const postImageFormBtns = document.getElementById('postImageFormBtns');
    const postImageProgrammerBtn = document.getElementById('postImageProgrammerBtn');
    const spinner = document.getElementById('imageProcessingSpinner');

    if (!imageModal || !importFileForm) {
        console.warn('Éléments modal image manquants');
        return;
    }

    importFileForm.addEventListener("submit", (event) => {
        event.preventDefault();

        const imageFileDataInput = document.getElementById('selectImageFile');
        const selectedFeed = document.querySelector('.row')?.getAttribute('data-selectedfeed');
        const newspaper = document.querySelector('.row')?.getAttribute('data-newspaper');
        const checkboxes = document.querySelectorAll('.network-checkbox_image');
        const currentDatetime = document.getElementById('current-datetime').dataset.currentDatetime;

        const imageFileData = {
            image_path: imageFileDataInput.value,
            imageFile: imageFileDataInput.files[0]
        };

        let previewImageSrc = '';

        // Lecture de l'image
        if (imageFileDataInput.files[0]) {
            const reader = new FileReader();
            reader.onload = (event) => {
                previewImageSrc = event.target.result;
            };
            reader.readAsDataURL(imageFileData.imageFile);
        }

        importFileForm.style.display = 'none';
        networkFormImage.style.display = 'block';
        postImageFormContainer.style.display = 'block';
        postImageFormBtns.style.display = 'block';

        // Génération du HTML des formulaires
        const generateFormHtml = (network) => {
            const headerColor = network === 'X' ? 'dark' : network === 'Threads' ? 'secondary' : network === 'Facebook' ? 'primary' : 'info';
            let networkFields;
            if (network === 'X') {
                networkFields = generateXFields(network);
            } else if (network === 'Threads') {
                networkFields = generateThreadsFields(network);
            } else if (network === 'Facebook') {
                networkFields = generateFacebookFields(network);
            } else {
                networkFields = generateBlueskyFields(network);
            }
            return `
                <div class="card mb-3">
                    <div class="card-header text-white bg-${headerColor}">
                        <strong>${network}</strong>
                    </div>
                    <div class="card-body">
                        <form action="/new_post_image" method="post">
                            <input type="hidden" name="network" value="${network}">
                            <input type="hidden" name="newspaper" value="${newspaper}">
                            <input type="hidden" name="selectedfeed" value="${selectedFeed}">
                            <input type="hidden" name="description" value="Non utilisé">
                            ${networkFields}
                        </form>
                    </div>
                </div>
            `;
        };

        const generateXFields = (network) => {
            return `
                        <div class="row">
                            <div class="col-7 border rounded p-2">
                                <label class="form-label fw-bold">Titre</label>
                                <textarea class="form-control" name="title" rows="2" required>Titre de l'article</textarea>
                                <div class="position-relative">
                                    <img src="${previewImageSrc}" class="w-100 mt-3 d-block rounded-3" alt="" />
                                </div>
                            </div>
                            <div class="col-5">
                                <label class="form-label fw-bold">Date et heure</label>
                                <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                            </div>
                        </div>
                        `;
        };

        const generateBlueskyFields = (network) => {
            return `
                        <input type="hidden" name="title" value="Non utilisé">
                            <div class="row">
                                <div class="col-7 border rounded p-2">
                                    <label class="form-label fw-bold">Accroche du post</label>
                                    <textarea class="form-control" name="tagline" rows="2" required>Accroche de l'article</textarea>
                                    <img src="${previewImageSrc}" class="w-100 mt-3 d-block rounded-3" alt="" />
                                </div>
                                <div class="col-5">
                                    <label class="form-label fw-bold">Date et heure</label>
                                    <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                                </div>
                            </div>
                            `;
        };

        const generateFacebookFields = (network) => {
            return `
                <div class="row">
                    <div class="col-7 border rounded p-2">
                        <label class="form-label fw-bold">Texte du post</label>
                        <textarea class="form-control" name="title" rows="3" maxlength="63206" required>Titre de l'article</textarea>
                        <div class="position-relative">
                            <img src="${previewImageSrc}" class="w-100 mt-3 d-block rounded-3" alt="" />
                        </div>
                    </div>
                    <div class="col-5">
                        <label class="form-label fw-bold">Date et heure</label>
                        <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                    </div>
                </div>
            `;
        };

        const generateThreadsFields = (network) => {
            return `
                        <div class="row">
                            <div class="col-7 border rounded p-2">
                                <label class="form-label fw-bold">Titre</label>
                                <textarea class="form-control" name="title" rows="2" required>Titre de l'article</textarea>
                                <div class="position-relative">
                                    <img src="${previewImageSrc}" class="w-100 mt-3 d-block rounded-3" alt="" />
                                </div>
                            </div>
                            <div class="col-5">
                                <label class="form-label fw-bold">Date et heure</label>
                                <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                            </div>
                        </div>
                        `;
        };


        // Regénération des formulaires de saisie des posts
        const regenerateForms = () => {
            const existingPostImageFormData = MedpostUtils.saveFormData(postImageFormContainer);
                            postImageFormContainer.innerHTML = '';

            checkboxes.forEach(checkbox => {
                if (checkbox.checked) {
                    const network = checkbox.value;
                            const formHtml = generateFormHtml(network);
                            postImageFormContainer.insertAdjacentHTML('beforeend', formHtml);
                }
            });

                            MedpostUtils.restoreFormData(postImageFormContainer, existingPostImageFormData);
        };

        checkboxes.forEach(checkbox => {
                                checkbox.addEventListener('change', regenerateForms);
        });

        // Validation et soumission des formulaires
        postImageProgrammerBtn.addEventListener('click', async () => {
            const forms = postImageFormContainer.querySelectorAll('form');

                            const success = await MedpostUtils.validateAndSubmitForms(forms, {
                                spinner,
                                imageFile: imageFileData.imageFile, // Image commune pour tous les formulaires
                onSuccess: () => {
                                window.location.href = `/?selectedfeed=tous&newspaper=${newspaper}`;
                },
                onError: (error) => {
                                console.error('Erreur lors de la programmation:', error);
                            alert('Erreur lors de la soumission des formulaires');
                }
            });
        });
    });
});