document.addEventListener('DOMContentLoaded', () => {
    const selectedFeed = document.querySelector('.row').getAttribute('data-selectedfeed');
    const importModal = document.getElementById('importLinkModal'); // fenêtre modale
    const importLinkForm = document.getElementById('importLinkForm'); // Formulaire lien à importer
    const submitLinkBtn = document.getElementById('submitLinkBtn') // Bouton importer le lien
    const networkFormContainer = document.getElementById('networkFormContainer'); // Formulaire sélection des réseaux
    const postFormContainer = document.getElementById('postFormContainer'); // Formulaire dynamique de création des posts
    const postFormButtons = document.getElementById('postFormButtons'); // Boutons Programmer/Anuuler
    const modifiedImages = {};
    
    // Fermeture de la modale et réinitialisation des éléments
    importModal.addEventListener('hidden.bs.modal', () => {
        console.log("Fermeture modale et reset");
        importLinkForm.reset();      
        responseMessage.style.display = "none";
        networkFormContainer.style.display = 'none';
        postFormContainer.style.display = 'none';
        importLinkForm.style.display = "block";
        // On réinitialise les checkboxes
        const checkboxes = document.querySelectorAll('.network-checkbox');
        if (checkboxes.length > 0) {
            checkboxes.forEach(checkbox => {
                checkbox.checked = false;
            });
        }
        postFormButtons.style.display = "none";
    });

    // Soumission du lien
    importLinkForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const responseMessage = document.getElementById('responseMessage');
        const newspaper = importLinkForm.dataset.newspaper;
        const formData = {
            importedLink: document.getElementById('importedLink').value,
            newspaper: newspaper
        };
        fetch('/import', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        })
        .then(response => {
            console.log(`HTTP Status Code: ${response.status}`);
            if (!response.ok) {
                throw new Error(`Erreur HTTP : ${response.status}`);
            }
            return response.json();
        })
        .then(importedArticle => {
            responseMessage.textContent = importedArticle.message || `Titre importé : ${importedArticle.title}`;
            responseMessage.style.display = "block";
            const spinner = document.getElementById('linkProcessingSpinner');
            console.log(importedArticle);
            // Formulaire de création de posts
            if (importedArticle.title && importedArticle.link && importedArticle.id && importedArticle.link && importedArticle.newspaper) {
                console.log("Données complètes");
                networkFormContainer.style.display = "block";

                // Affichage des formulaires réseaux
                // const postFormContainer = document.getElementById('postFormContainer');
                const checkboxes = document.querySelectorAll('.network-checkbox');
                const postProgrammerBtn = document.getElementById('postProgrammerBtn');
                
                importLinkForm.style.display = "none"; // On cache le formulaire de saisie du lien
                postFormButtons.style.display = "block"; // On affiche les boutons Programmer/Annuler
                postFormContainer.style.display = 'block';

                // Sauvegarde des formulaires pour chaque réseau sélectionné
                const saveFormData = (postFormContainer) => {
                    const formData = {};
                    postFormContainer.querySelectorAll('form').forEach(form => {
                        const network = form.querySelector('input[name="network"]').value;
                        formData[network] = {};
                        form.querySelectorAll('textarea, input').forEach(field => {
                            if (field.name) {
                                formData[network][field.name] = field.value;
                            }
                        });
                        console.log("Données sauvegardées : ", formData[network]);
                    });
                    return formData;
                };

                // Réinitialisation des formulaires lors de l'ouverture de modale
                let isModalInitialized = false;
                importModal.addEventListener('shown.bs.modal', () => {
                    if (!isModalInitialized) {
                        regenerateForms(); 
                        isModalInitialized = true;
                    }
                });

                // Restauration des formulaires
                const restoreFormData = (postFormContainer, formData) => {
                    postFormContainer.querySelectorAll('form').forEach(form => {
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
                    const existingFormData = saveFormData(postFormContainer);
                    postFormContainer.innerHTML = '';  // Effacer les formulaires existants
                    checkboxes.forEach(checkbox => {
                        if (checkbox.checked) {
                            const network = checkbox.value;
                            const formId = `form-${network}-imported`;
                            const currentDatetime = document.getElementById('current-datetime').dataset.currentDatetime;

                            const form = document.createElement('div');
                            form.id = formId;
                            form.className = 'card mb-3';

                            form.innerHTML = `
                                   <div class="card-header text-white bg-${network === 'X' ? 'dark' : network === 'Bluesky' ? 'info' : 'primary'}">
                                        <strong>${network}</strong>
                                    </div>
                                    <div class="card-body">
                                        <form action="/new_post" method="post">
                                            <input type="hidden" name="network" value="${network}">
                                            <input type="hidden" name="newspaper" value="${newspaper}">
                                            <input type="hidden" name="selectedfeed" value="${selectedFeed}">
                                            <input type="hidden" name="image_url" value="${importedArticle.image_url}">
                                            <input type="hidden" name="article_id" value="${importedArticle.id}">
                                            <input type="hidden" name="description" value="${importedArticle.summary}">
                                            ${
                                                network == 'X'
                                                ? `
                                                    <div class="row">
                                                        <div class="col-7 border rounded p-2">
                                                            <label class="form-label fw-bold">Titre</label>
                                                            <textarea class="form-control" name="title" rows="2" required>${importedArticle.title}</textarea>
                                                            <div class="position-relative">
                                                                <img id="previewImage_${network}" src="${modifiedImages[network]?.url || importedArticle.image_url}" class="w-100 mt-3 d-block rounded-3" alt=""/>
                                                                <a href="${importedArticle.link}" class="card-link" target="_blank">De lequotidiendumedecin.fr</a>
                                                            </div>
                                                        </div>
                                                        <div class="col-5">
                                                            <label class="form-label fw-bold">Date et heure</label>
                                                            <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                                                `
                                                : `
                                                    <input type="hidden" name="title" value="${importedArticle.title}">
                                                    <div class="row">
                                                        <div class="col-7 border rounded p-2">
                                                            <label for="description_${network}" class="form-label fw-bold">Accroche du post</label>
                                                            <textarea class="form-control" id="tagline_${network}" name="tagline" rows="2" required></textarea>
                                                            <img id="previewImage_${network}" src="${modifiedImages[network]?.url || importedArticle.image_url}" class="w-100 mt-3 d-block rounded-3" alt=""/>
                                                            <div class="legend-title">${importedArticle.title}</div>
                                                            <div class="legend-chapo">${importedArticle.summary.length > 165 ? importedArticle.summary.substring(0, 165) + '...' : importedArticle.summary}</div>
                                                            <a href="${importedArticle.link}" class="card-link" target="_blank">@ www.lequotidiendupharmacien.fr</a>
                                                        </div>
                                                        <div class="col-5">
                                                            <label class="form-label fw-bold">Date et heure</label>
                                                            <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                                                `
                                            }
                                                            <label for="modifyImageFormFile_${network}" class="form-label fw-bold">Modifier l'image</label>
                                                            <input type="file" class="form-control mb-3" id="modifyImageFormFile_${network}" accept="image/*">
                                                            <button type="button" class="btn btn-primary" id="modifyImageBtn_${network}">Upload</button>
                                                        </div>
                                                    </div>
                                        </form>
                                    </div>
                                </div>
                            `;
                            postFormContainer.appendChild(form);

                            // Upload d'un fichier image
                            const uploadImageBtn = document.getElementById(`modifyImageBtn_${network}`);
                            const fileInputForm = document.getElementById(`modifyImageFormFile_${network}`);
                            const previewImageElement = document.getElementById(`previewImage_${network}`);
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
                                        urlData = event.target.result; // URL de données
                                        previewImageElement.src = urlData;
                                        // Stocker le chemin de l'image modifiée
                                        if (!modifiedImages[network]) {
                                            modifiedImages[network] = {};
                                        };
                                        modifiedImages[network] = {
                                            file: imageFile,
                                            url: urlData
                                        };
                                    };
                                    reader.readAsDataURL(imageFile);
                                    // imageUrlInput.value = imageFile.name;
                                }
                            });

                        }
                    });
                    restoreFormData(postFormContainer, existingFormData);
                };

                checkboxes.forEach(checkbox => {
                    checkbox.addEventListener('change', () => {
                        regenerateForms();
                    });
                });

                postProgrammerBtn.addEventListener('click', () => {
                    const forms = postFormContainer.querySelectorAll('form');
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
                        spinner.style.display = 'block'; // Affiche le spinner
                        const promises = [];
                        forms.forEach(form => {
                            const formData = new FormData(form);
                            const network = form.querySelector('input[name="network"]').value;
                            // Ajouter le fichier image au FormData
                            if (modifiedImages[network]) {
                                const imageFile = modifiedImages[network].file;
                                formData.append('imageFile', imageFile); // Ajout du fichier image
                            }
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
            } else {
                // Données du serveur incomplètes
                console.log("Données incomplètes lors de l'import");
            }
        })
        .catch(error => {
            console.error("Erreur lors de l'importation :", error);
            responseMessage.textContent = `Erreur : ${error.message}`;
            responseMessage.style.display = "block";
        });
    });


})