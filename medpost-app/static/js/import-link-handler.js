document.addEventListener('DOMContentLoaded', () => {
    const importModal = document.getElementById('importLinkModal'); // fenêtre modale
    const importLinkForm = document.getElementById('importLinkForm'); // Formulaire lien à importer
    const submitLinkBtn = document.getElementById('submitLinkBtn') // Bouton importer le lien
    const networkFormContainer = document.getElementById('networkFormContainer'); // Formulaire sélection des réseaux
    const postFormContainer = document.getElementById('postFormContainer'); // Formulaire dynamique de création des posts
    const postFormButtons = document.getElementById('postFormButtons'); // Boutons Programmer/Anuuler
    
    // Fermeture de la modale et réinitialisation des éléments
    importModal.addEventListener('hidden.bs.modal', () => {
        console.log("Fermeture modale et reset");
        importLinkForm.reset();      
        responseMessage.style.display = "none";
        networkFormContainer.style.display = 'none';
        postFormContainer.style.display = 'none'
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
            console.log(importedArticle);
            // Formulaire de création de posts
            if (importedArticle.title && importedArticle.summary && importedArticle.link && importedArticle.id && importedArticle.link && importedArticle.newspaper) {
                console.log("Données complètes");
                networkFormContainer.style.display = "block";

                // Affichage des formulaires réseaux
                const postFormContainer = document.getElementById('postFormContainer');
                const checkboxes = document.querySelectorAll('.network-checkbox');
                const postProgrammerBtn = document.getElementById('postProgrammerBtn');
                
                importLinkForm.style.display = "none"; // On cache le formulaire de saisie du lien
                postFormButtons.style.display = "block"; // On affiche les boutons Programmer/Annuler
                postFormContainer.style.display = 'block';

                const regenerateForms = () => {
                    postFormContainer.innerHTML = '';  // Effacer les formulaires existants
                    checkboxes.forEach(checkbox => {
                        if (checkbox.checked) {
                            const network = checkbox.value;
                            const formId = `form-${network}-imported`;
                            const currentDatetime = document.getElementById('current-datetime').dataset.currentDatetime;
                            console.log("Date : ", currentDatetime)

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
                                            <input type="hidden" name="image_url" value="${importedArticle.image_url}">
                                            <input type="hidden" name="article_id" value="${importedArticle.id}">
                                            <div class="mb-3">
                                                <img src="${importedArticle.image_url}" class="img-fluid me-3" style="max-width: 50px;" alt=""/>
                                                <label class="form-label fw-bold">Titre</label>
                                                <textarea class="form-control" name="title" rows="3" required>${importedArticle.title}</textarea>
                                            </div>
                                            ${
                                                network !== 'X'
                                                    ? `
                                                    <div class="mb-3">
                                                        <label for="description_${network}" class="form-label fw-bold">Description du post</label>
                                                        <textarea class="form-control" id="description_${network}" name="description" rows="3" required>${importedArticle.summary}</textarea>
                                                    </div>
                                                    <div class="mb-3">
                                                        <label for="tagline_${network}" class="form-label fw-bold">Accroche du post</label>
                                                        <textarea class="form-control" id="tagline_${network}" name="tagline" rows="3" required></textarea>
                                                    </div>
                                                    `
                                                    : ''
                                            }
                                            <div class="mb-3">
                                                <label class="form-label fw-bold">Lien</label>
                                                <input type="text" class="form-control" name="link" value="${importedArticle.link}" required>
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label fw-bold">Date et heure</label>
                                                <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                                            </div>
                                        </form>
                                    </div>
                                </div>
                            `;
                            postFormContainer.appendChild(form);
                        }
                    });
                };

                checkboxes.forEach(checkbox => {
                    checkbox.addEventListener('change', () => {
                        regenerateForms();
                    });
                });

                postProgrammerBtn.addEventListener('click', () => {
                    const forms = postFormContainer.querySelectorAll('form');
                    console.log("Form", forms)
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