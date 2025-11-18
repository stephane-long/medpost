document.addEventListener('DOMContentLoaded', () => {
    const selectedFeed = document.querySelector('.row')?.getAttribute('data-selectedfeed');
    const newspaper = document.querySelector('.row')?.getAttribute('data-newspaper');
    const modifiedImages = {}; // Structure: { modalId: { network: { file, url } } }
    const spinner = document.getElementById('newPostProcessingSpinner');
    
    document.querySelectorAll('[id^="newpost"]').forEach(modalElement => {
        const modalId = modalElement.id.replace('newpost', '');
        const container = document.getElementById(`dynamic-forms-container${modalId}`);
        const checkboxes = document.querySelectorAll(`#newpost${modalId} .network-checkbox`);
        const programmerButton = document.getElementById(`programmer-btn-${modalId}`);

        if (!container || !programmerButton) {
            console.warn(`Éléments manquants pour modal ${modalId}`);
            return;
        }

        // Données de l'article depuis data-* attributes
        const articleData = {
            title: modalElement.getAttribute('data-title') || '',
            description: modalElement.getAttribute('data-description') || '',
            link: modalElement.getAttribute('data-link') || '',
            minDatetime: modalElement.getAttribute('data-min-datetime') || '',
            imageUrl: modalElement.getAttribute('data-image-url') || ''
        };

        let isModalInitialized = false;
        
        // Initialisation au premier affichage de la modale
        modalElement.addEventListener('shown.bs.modal', () => {
            if (!isModalInitialized) {
                regenerateForms(); 
                isModalInitialized = true;
            }
        });

        // Génération du HTML pour les formulaires réseau
        const generateFormHtml = (network, modalId, data) => {
            const modifiedImage = modifiedImages[modalId]?.[network];
            const imageSrc = modifiedImage?.url || data.imageUrl;
            
            return `
                <div class="card mb-3">
                    <div class="card-header text-white bg-${network === 'X' ? 'dark' : network === 'Bluesky' ? 'info' : 'primary'}">
                        <strong>${network}</strong>
                    </div>
                    <div class="card-body">
                        <form action="/new_post" method="post" enctype="multipart/form-data">
                            <input type="hidden" name="article_id" value="${modalId}">
                            <input type="hidden" name="network" value="${network}">
                            <input type="hidden" name="selectedfeed" value="${selectedFeed}">
                            <input type="hidden" name="newspaper" value="${newspaper}">
                            <input type="hidden" name="description" value="${MedpostUtils.escapeHtml(data.description)}">
                            <input type="hidden" name="image_url" value="${data.imageUrl}">
                            ${network === 'X' ? generateXFields(network, modalId, data, imageSrc) 
                                              : generateBlueskyFields(network, modalId, data, imageSrc)}
                        </form>
                    </div>
                </div>
            `;
        };
        
        // Génération des champs spécifiques à X
        const generateXFields = (network, modalId, data, imageSrc) => {
            return `
                <div class="row">
                    <div class="col-8 border rounded p-2">
                        <label for="title_${network}_${modalId}" class="form-label fw-bold">Titre du post</label>
                        <textarea class="form-control" id="title_${network}_${modalId}" name="title" rows="2" required>${MedpostUtils.escapeHtml(data.title)}</textarea>                                                
                        <div class="position-relative">
                            <img id="previewImage_${network}_${modalId}" src="${imageSrc}" class="w-100 mt-3 d-block rounded-3" alt=""/>
                            <div id="caption_${network}_${modalId}" class="legend position-absolute start-50 translate-middle-x rounded bg-dark bg-opacity-75 text-white py-1 px-2 text-truncate">
                                ${MedpostUtils.escapeHtml(data.title)}
                            </div>
                            <a href="${data.link}" class="card-link" target="_blank">De lequotidiendumedecin.fr</a>
                        </div>
                    </div>
                    <div class="col-4">
                        <label for="date_${network}_${modalId}" class="form-label fw-bold">Date et heure</label>
                        <input type="datetime-local" class="form-control mb-3" id="date_${network}_${modalId}" name="datetime" value="${data.minDatetime}" min="${data.minDatetime}" style="width: 250px;" required>
                        <label for="modifyImageFormFile_${network}_${modalId}" class="form-label fw-bold">Modifier l'image</label>
                        <input type="file" class="form-control mb-3" id="modifyImageFormFile_${network}_${modalId}" accept="image/*">
                        <button type="button" class="btn btn-primary" id="modifyImageBtn_${network}_${modalId}">Upload</button>
                    </div>
                </div>
            `;
        };
        
        // Génération des champs spécifiques à Bluesky
        const generateBlueskyFields = (network, modalId, data, imageSrc) => {
            const truncatedDesc = MedpostUtils.truncateText(data.description, 165);
            return `
                <input type="hidden" name="title" value="${MedpostUtils.escapeHtml(data.title)}">
                <div class="row">
                    <div class="col-8 border rounded p-2">
                        <label for="tagline_${network}_${modalId}" class="form-label fw-bold">Accroche du post</label>
                        <textarea class="form-control" id="tagline_${network}_${modalId}" name="tagline" rows="2" required></textarea>
                        <img id="previewImage_${network}_${modalId}" src="${imageSrc}" class="w-100 mt-3 rounded mb-2" alt=""/>
                        <div class="legend-title">${MedpostUtils.escapeHtml(data.title)}</div>
                        <div class="legend-chapo">${MedpostUtils.escapeHtml(truncatedDesc)}</div>
                        <a href="${data.link}" class="card-link" target="_blank">@ www.lequotidiendupharmacien.fr</a>
                    </div>
                    <div class="col-4">
                        <label for="date_${network}_${modalId}" class="form-label fw-bold">Date et heure</label>
                        <input type="datetime-local" class="form-control" id="date_${network}_${modalId}" name="datetime" value="${data.minDatetime}" min="${data.minDatetime}" style="width: 250px;" required>
                        <label for="modifyImageFormFile_${network}_${modalId}" class="form-label fw-bold">Modifier l'image</label>
                        <input type="file" class="form-control mb-3" id="modifyImageFormFile_${network}_${modalId}" accept="image/*">
                        <button type="button" class="btn btn-primary" id="modifyImageBtn_${network}_${modalId}">Upload</button>
                    </div>
                </div>
            `;
        };

        const regenerateForms = () => {
            // Sauvegarder les données existantes
            const existingFormData = MedpostUtils.saveFormData(container);
            container.innerHTML = '';
            
            checkboxes.forEach(checkbox => {
                if (checkbox.checked) {
                    const network = checkbox.value;
                    const formHtml = generateFormHtml(network, modalId, articleData);
                    container.insertAdjacentHTML('beforeend', formHtml);
                    
                    // Attacher les handlers d'upload d'image
                    MedpostUtils.attachImageUploadHandlers(network, modalId, modifiedImages);
                }
            });
            
            // Restaurer les données
            MedpostUtils.restoreFormData(container, existingFormData);
        };

        // Regénération des formulaires en cas de checkbox cochée
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', regenerateForms);
        });
        
        // Soumission des formulaires
        if (programmerButton) {
            programmerButton.addEventListener('click', async () => {
                const forms = container.querySelectorAll('form');
                
                const success = await MedpostUtils.validateAndSubmitForms(forms, {
                    spinner,
                    modifiedImages,
                    modalId,
                    onSuccess: () => {
                        window.location.href = `/?selectedfeed=${selectedFeed}&newspaper=${newspaper}`;
                    },
                    onError: (error) => {
                        console.error('Erreur lors de la programmation:', error);
                        alert('Erreur lors de la soumission des formulaires');
                    }
                });
            });
        }
    });
});
