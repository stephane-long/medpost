document.addEventListener('DOMContentLoaded', () => {
    const selectedFeed = document.querySelector('.row')?.getAttribute('data-selectedfeed');
    const importModal = document.getElementById('importLinkModal');
    const importLinkForm = document.getElementById('importLinkForm');
    const submitLinkBtn = document.getElementById('submitLinkBtn');
    const networkFormContainer = document.getElementById('networkFormContainer');
    const postFormContainer = document.getElementById('postFormContainer');
    const postFormButtons = document.getElementById('postFormButtons');
    const responseMessage = document.getElementById('responseMessage');
    const spinner = document.getElementById('linkProcessingSpinner');
    const modifiedImages = {}; // Structure: { network: { file, url } }
    
    if (!importModal || !importLinkForm) {
        console.warn('Éléments importLinkModal manquants');
        return;
    }
    
    // Fermeture de la modale et réinitialisation des éléments
    importModal.addEventListener('hidden.bs.modal', () => {
        console.log("Fermeture modale et reset");
        importLinkForm.reset();      
        responseMessage.style.display = "none";
        networkFormContainer.style.display = 'none';
        postFormContainer.style.display = 'none';
        importLinkForm.style.display = "block";
        
        // Réinitialiser les checkboxes
        const checkboxes = document.querySelectorAll('.network-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        
        postFormButtons.style.display = "none";
        
        // Vider les images modifiées
        Object.keys(modifiedImages).forEach(key => delete modifiedImages[key]);
    });

    // Soumission du lien
    importLinkForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        
        const newspaper = importLinkForm.dataset.newspaper;
        const importedLink = document.getElementById('importedLink').value;
        
        const formData = {
            importedLink: importedLink,
            newspaper: newspaper
        };
        
        try {
            const response = await fetch('/import', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });
            
            console.log(`HTTP Status Code: ${response.status}`);
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP : ${response.status}`);
            }
            
            const importedArticle = await response.json();
            
            responseMessage.textContent = importedArticle.message || `Titre importé : ${importedArticle.title}`;
            responseMessage.style.display = "block";
            
            console.log('Article importé:', importedArticle);
            
            // Formulaire de création de posts si données complètes
            if (importedArticle.title && importedArticle.id && importedArticle.newspaper) {
                console.log("Données complètes - affichage formulaires");
                
                networkFormContainer.style.display = "block";
                importLinkForm.style.display = "none";
                postFormButtons.style.display = "block";
                postFormContainer.style.display = 'block';
                
                const checkboxes = document.querySelectorAll('.network-checkbox');
                const postProgrammerBtn = document.getElementById('postProgrammerBtn');
                
                let isModalInitialized = false;
                
                // Initialisation des formulaires au premier affichage
                importModal.addEventListener('shown.bs.modal', () => {
                    if (!isModalInitialized) {
                        regenerateForms(); 
                        isModalInitialized = true;
                    }
                });
                
                // Génération du HTML des formulaires
                const generateFormHtml = (network) => {
                    const currentDatetime = document.getElementById('current-datetime').dataset.currentDatetime;
                    const modifiedImage = modifiedImages[network];
                    const imageSrc = modifiedImage?.url || importedArticle.image_url;
                    
                    return `
                        <div class="card mb-3">
                            <div class="card-header text-white bg-${network === 'X' ? 'dark' : network === 'Threads' ? 'secondary' : network === 'Facebook' ? 'primary' : 'info' }">
                                <strong>${network}</strong>
                            </div>
                            <div class="card-body">
                                <form action="/new_post" method="post">
                                    <input type="hidden" name="network" value="${network}">
                                    <input type="hidden" name="newspaper" value="${newspaper}">
                                    <input type="hidden" name="selectedfeed" value="${selectedFeed}">
                                    <input type="hidden" name="image_url" value="${importedArticle.image_url}">
                                    <input type="hidden" name="article_id" value="${importedArticle.id}">
                                    <input type="hidden" name="description" value="${MedpostUtils.escapeHtml(importedArticle.summary)}">
                                    ${network === 'X' ? generateXFields(network, imageSrc, currentDatetime)
                                        : network === 'Threads' ? generateThreadsFields(network, imageSrc, currentDatetime)
                                        : network === 'Facebook' ? generateFacebookFields(network, imageSrc, currentDatetime)
                                        : generateBlueskyFields(network, imageSrc, currentDatetime)}
                                </form>
                            </div>
                        </div>
                    `;
                };
                
                // Champs spécifiques X
                const generateXFields = (network, imageSrc, currentDatetime) => {
                    return `
                        <div class="row">
                            <div class="col-7 border rounded p-2">
                                <label class="form-label fw-bold">Titre du post</label>
                                <textarea class="form-control" name="title" rows="2" required>${MedpostUtils.escapeHtml(importedArticle.title)}</textarea>
                                <div class="position-relative">
                                    <img id="previewImage_${network}_import-link" src="${imageSrc}" class="w-100 mt-3 d-block rounded-3" alt=""/>
                                    <a href="${importedArticle.link}" class="card-link" target="_blank">De ${newspaper === 'qdm' ? 'lequotidiendumedecin.fr' : 'lequotidiendupharmacien.fr'}</a>
                                </div>
                            </div>
                            <div class="col-5">
                                <label class="form-label fw-bold">Date et heure</label>
                                <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                                <label for="modifyImageFormFile_${network}_import-link" class="form-label fw-bold">Modifier l'image</label>
                                <input type="file" class="form-control mb-3" id="modifyImageFormFile_${network}_import-link" accept="image/*">
                                <button type="button" class="btn btn-primary" id="modifyImageBtn_${network}_import-link">Upload</button>
                            </div>
                        </div>
                    `;
                };
                
                // Champs spécifiques Bluesky
                const generateBlueskyFields = (network, imageSrc, currentDatetime) => {
                    const truncatedSummary = MedpostUtils.truncateText(importedArticle.summary, 165);
                    return `
                        <input type="hidden" name="title" value="${MedpostUtils.escapeHtml(importedArticle.title)}">
                        <div class="row">
                            <div class="col-7 border rounded p-2">
                                <label class="form-label fw-bold">Accroche du post</label>
                                <textarea class="form-control" name="tagline" rows="2" required></textarea>
                                <img id="previewImage_${network}_import-link" src="${imageSrc}" class="w-100 mt-3 d-block rounded-3" alt=""/>
                                <div class="legend-title">${MedpostUtils.escapeHtml(importedArticle.title)}</div>
                                <div class="legend-chapo">${MedpostUtils.escapeHtml(truncatedSummary)}</div>
                                <a href="${importedArticle.link}" class="card-link" target="_blank">@ www.${newspaper === 'qdm' ? 'lequotidiendumedecin.fr' : 'lequotidiendupharmacien.fr'}</a>
                            </div>
                            <div class="col-5">
                                <label class="form-label fw-bold">Date et heure</label>
                                <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                                <label for="modifyImageFormFile_${network}_import-link" class="form-label fw-bold">Modifier l'image</label>
                                <input type="file" class="form-control mb-3" id="modifyImageFormFile_${network}_import-link" accept="image/*">
                                <button type="button" class="btn btn-primary" id="modifyImageBtn_${network}_import-link">Upload</button>
                            </div>
                        </div>
                    `;
                };

                // Champs spécifiques Facebook
                const generateFacebookFields = (network, imageSrc, currentDatetime) => {
                    const truncatedSummary = MedpostUtils.truncateText(importedArticle.summary, 165);
                    return `
                        <input type="hidden" name="title" value="${MedpostUtils.escapeHtml(importedArticle.title)}">
                        <div class="row">
                            <div class="col-7 border rounded p-2">
                                <label class="form-label fw-bold">Accroche du post</label>
                                <textarea class="form-control" name="tagline" rows="3" maxlength="63206" required></textarea>
                                <img id="previewImage_${network}_import-link" src="${imageSrc}" class="w-100 mt-3 d-block rounded-3" alt=""/>
                                <div class="legend-title">${MedpostUtils.escapeHtml(importedArticle.title)}</div>
                                <div class="legend-chapo">${MedpostUtils.escapeHtml(truncatedSummary)}</div>
                                <a href="${importedArticle.link}" class="card-link" target="_blank">@ www.${newspaper === 'qdm' ? 'lequotidiendumedecin.fr' : 'lequotidiendupharmacien.fr'}</a>
                            </div>
                            <div class="col-5">
                                <label class="form-label fw-bold">Date et heure</label>
                                <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                                <label for="modifyImageFormFile_${network}_import-link" class="form-label fw-bold">Modifier l'image</label>
                                <input type="file" class="form-control mb-3" id="modifyImageFormFile_${network}_import-link" accept="image/*">
                                <button type="button" class="btn btn-primary" id="modifyImageBtn_${network}_import-link">Upload</button>
                            </div>
                        </div>
                    `;
                };

                // Champs spécifiques Threads
                const generateThreadsFields = (network, imageSrc, currentDatetime) => {
                    const truncatedSummary = MedpostUtils.truncateText(importedArticle.summary, 165);
                    return `
                        <input type="hidden" name="title" value="${MedpostUtils.escapeHtml(importedArticle.title)}">
                        <div class="row">
                            <div class="col-7 border rounded p-2">
                                <label class="form-label fw-bold">Titre du post</label>
                                <textarea class="form-control" name="title" rows="2" required>${MedpostUtils.escapeHtml(importedArticle.title)}</textarea>
                                <img id="previewImage_${network}_import-link" src="${imageSrc}" class="w-100 mt-3 d-block rounded-3" alt=""/>
                                <div class="legend-title">${MedpostUtils.escapeHtml(importedArticle.title)}</div>
                                <div class="legend-chapo">${MedpostUtils.escapeHtml(truncatedSummary)}</div>
                                <a href="${importedArticle.link}" class="card-link" target="_blank">@ www.${newspaper === 'qdm' ? 'lequotidiendumedecin.fr' : 'lequotidiendupharmacien.fr'}</a>
                            </div>
                            <div class="col-5">
                                <label class="form-label fw-bold">Date et heure</label>
                                <input type="datetime-local" class="form-control" name="datetime" value="${currentDatetime}" min="${currentDatetime}" style="width: 250px;" required>
                                <label for="modifyImageFormFile_${network}_import-link" class="form-label fw-bold">Modifier l'image</label>
                                <input type="file" class="form-control mb-3" id="modifyImageFormFile_${network}_import-link" accept="image/*">
                                <button type="button" class="btn btn-primary" id="modifyImageBtn_${network}_import-link">Upload</button>
                            </div>
                        </div>
                    `;
                };
        
                const regenerateForms = () => {
                    const existingFormData = MedpostUtils.saveFormData(postFormContainer);
                    postFormContainer.innerHTML = '';
                    
                    checkboxes.forEach(checkbox => {
                        if (checkbox.checked) {
                            const network = checkbox.value;
                            const formHtml = generateFormHtml(network);
                            postFormContainer.insertAdjacentHTML('beforeend', formHtml);
                            
                            // Attacher les handlers d'upload d'image (sans modalId pour import-link)
                            MedpostUtils.attachImageUploadHandlers(network, 'import-link', modifiedImages);
                        }
                    });
                    
                    MedpostUtils.restoreFormData(postFormContainer, existingFormData);
                };

                checkboxes.forEach(checkbox => {
                    checkbox.addEventListener('change', regenerateForms);
                });

                postProgrammerBtn.addEventListener('click', async () => {
                    const forms = postFormContainer.querySelectorAll('form');
                    
                    const success = await MedpostUtils.validateAndSubmitForms(forms, {
                        spinner,
                        modifiedImages,
                        modalId: 'import-link',
                        onSuccess: () => {
                            window.location.href = `/?selectedfeed=tous&newspaper=${newspaper}`;
                        },
                        onError: (error) => {
                            console.error('Erreur lors de la programmation:', error);
                            alert('Erreur lors de la soumission des formulaires');
                        }
                    });
                });
            } else {
                // Données du serveur incomplètes
                console.log("Données incomplètes lors de l'import");
            }
        } catch (error) {
            console.error("Erreur lors de l'importation :", error);
            responseMessage.textContent = `Erreur : ${error.message}`;
            responseMessage.style.display = "block";
        }
    });
});