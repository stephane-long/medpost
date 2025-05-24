document.addEventListener('DOMContentLoaded', () => {
    const imageModal = document.getElementById('importImage'); // Fenêtre modale
    const importFileForm = document.getElementById('importFileForm'); // Formulaire de sélection du fichier image
    const submitFileBtn = document.getElementById('submitFileBtn'); // Bouton import du fichier
    const networkFormImage = document.getElementById('networkForm_image'); // Check box réseau
    const postImageFormContainer = document.getElementById('postImageFormContainer'); // Formulaire dynamique de création des posts

    importFileForm.addEventListener("submit", (event) => {  // Soumission du fichier image
        event.preventDefault();
        const imageFileDataInput = document.getElementById('selectImageFile'); // Fichier soumis
        const selectedFeed = document.querySelector('.row').getAttribute('data-selectedfeed');
        const newspaper = document.querySelector('.row').getAttribute('data-newspaper');
        const checkboxes = document.querySelectorAll('.network-checkbox_image');
        const currentDatetime = document.getElementById('current-datetime').dataset.currentDatetime;
        const postImageFormBtns = document.getElementById('postImageFormBtns'); // Container Bouton de programmation des formulaires
        const postImageProgrammerBtn = document.getElementById('postImageProgrammerBtn');


        const imageFileData = {
            image_path: imageFileDataInput.value,
            imageFile: imageFileDataInput.files[0]
        }
        let previewImageSrc; //URL de l'image
        // Lecture e l'image
        if (imageFileDataInput) {
            const reader = new FileReader();
            reader.onload = (event) => {
                urlData = event.target.result; // URL de données
                previewImageSrc = urlData;
            };
            reader.readAsDataURL(imageFileData.imageFile);
        }
        importFileForm.style.display = 'none';
        networkFormImage.style.display='block';
        postImageFormContainer.style.display = 'block';
        postImageFormBtns.style.display = 'block';


        // Sauvegarde des formulaires pour chaque réseau sélectionné
        const savePostImageFormData = (postImageFormContainer) => {
            const postImageFormData = {};
            postImageFormContainer.querySelectorAll('form').forEach(form => {
                const network = form.querySelector('input[name="network"]').value;
                postImageFormData[network] = {};
                form.querySelectorAll('textarea, input').forEach(field => {
                    if (field.name) {
                        postImageFormData[network][field.name] = field.value;
                    }
                });
                console.log("Données sauvegardées : ", postImageFormData[network]);
            });
            return postImageFormData;
        };

        // Restauration des formulaires
        const restorePostImageFormData = (postImageFormContainer, postImageFormData) => {
            postImageFormContainer.querySelectorAll('form').forEach(form => {
                const network = form.querySelector('input[name="network"]').value;
                if (postImageFormData[network]) {
                    form.querySelectorAll('textarea, input').forEach(field => {
                        if (field.name && postImageFormData[network][field.name] !== undefined) {
                            field.value = postImageFormData[network][field.name];
                        }
                    });
                }
            });
        };

        // Regénération des formulaires de saisie des posts
        const regenerateForms = () => {
            const existingPostImageFormData = savePostImageFormData(postImageFormContainer);
            postImageFormContainer.innerHTML = '';
            checkboxes.forEach(checkbox => {
                if (checkbox.checked) {
                    const network = checkbox.value;
                    const formId = `form-${network}-postImage`;
                    const form = document.createElement('div');
                    form.id = formId;
                    form.className = 'card mb-3';

                    form.innerHTML = `
                            <div class="card-header text-white bg-${network === 'X' ? 'dark' : network === 'Bluesky' ? 'info' : 'primary'}">
                                <strong>${network}</strong>
                            </div>
                            <div class="card-body">
                                <form action="/new_post_image" method="post">
                                    <input type="hidden" name="network" value="${network}">
                                    <input type="hidden" name="newspaper" value="${newspaper}">
                                    <input type="hidden" name="selectedfeed" value="${selectedFeed}">
                                    <input type="hidden" name="description" value="">
                                    ${
                                        network == 'X'
                                        ? `
                                            <div class="row">
                                                <div class="col-7 border rounded p-2">
                                                    <label class="form-label fw-bold">Titre</label>
                                                    <textarea class="form-control" name="title" rows="2" required>Titre de l'article</textarea>
                                                    <div class="position-relative">
                                                        <img src="${previewImageSrc}" class="w-100 mt-3 d-block rounded-3" alt=""/>
                                                    </div>
                                                </div>
                                                <div class="col-5">
                                                    <label class="form-label fw-bold">Date et heure</label>
                                                    <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                                        `
                                        : `
                                            <input type="hidden" name="title" value="">
                                            <div class="row">
                                                <div class="col-7 border rounded p-2">
                                                    <label class="form-label fw-bold">Accroche du post</label>
                                                    <textarea class="form-control" name="tagline" rows="2" required></textarea>
                                                    <img src="${previewImageSrc}" class="w-100 mt-3 d-block rounded-3" alt=""/>
                                                </div>
                                                <div class="col-5">
                                                    <label class="form-label fw-bold">Date et heure</label>
                                                    <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                                        `
                                    }
                                                </div>
                                            </div>
                                </form>
                            </div>
                        </div>
                    `;
                    postImageFormContainer.appendChild(form);

                };
            });
            restorePostImageFormData(postImageFormContainer, existingPostImageFormData);
        };
        
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                regenerateForms();
            });
        });

        // Validation des formulaires
        postImageProgrammerBtn.addEventListener('click', () => {
            console.log("Programmer cliqué")
            const forms = postImageFormContainer.querySelectorAll('form');
            let allValid = true;

            forms.forEach(form => {
                if (!form.checkValidity()) {
                    allValid = false;
                    form.querySelectorAll(':invalid').forEach(field => {
                        field.classList.add('is-invalid');
                        field.addEventListener('input', () => {
                            field.classList.remove('is-invalid');
                        });
                    });
                }
            });

            if (allValid) {
                const promises = [];
                forms.forEach(form => {
                    const formData = new FormData(form);
                    const network = form.querySelector('input[name="network"]').value;
                    console.log("Envoi du formulaire")
                    // Ajout de l'image
                    const imageFile = imageFileData.imageFile;
                    formData.append('imageFile', imageFile); // Ajout du fichier image
                    const promise = fetch(form.action, {
                        method: form.method,
                        body: formData,
                    });
                    promises.push(promise);
                });
                
                Promise.all(promises)
                .then(responses => {
                    const allSuccessful = responses.every(response => response.ok);
                    if (allSuccessful) {
                        window.location.href = `/?selectedfeed=tous&newspaper=${newspaper}`;
                    } else {
                        console.error("Échec sur une plusieurs soumissions.");
                    }
                })
                .catch(error => {
                    console.error("Erreur lors des soumissions :", error);
                });
            }            
        });
    });
})