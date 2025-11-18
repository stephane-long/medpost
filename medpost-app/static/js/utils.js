/**
 * MedpostUtils - Utilitaires réutilisables pour l'application Medpost
 * Pattern IIFE pour éviter la pollution du scope global
 */
const MedpostUtils = (function() {
    'use strict';
    
    /**
     * Sauvegarde les données de tous les formulaires d'un container
     * @param {HTMLElement} container - Conteneur des formulaires
     * @returns {Object} Données des formulaires indexées par réseau
     */
    function saveFormData(container) {
        const formData = {};
        
        container.querySelectorAll('form').forEach(form => {
            const networkInput = form.querySelector('input[name="network"]');
            if (!networkInput) return;
            
            const network = networkInput.value;
            formData[network] = {};
            
            form.querySelectorAll('textarea, input').forEach(field => {
                if (field.name && field.name !== 'network') {
                    formData[network][field.name] = field.value;
                }
            });
        });
        
        return formData;
    }
    
    /**
     * Restaure les données sauvegardées dans les formulaires
     * @param {HTMLElement} container - Conteneur des formulaires
     * @param {Object} formData - Données à restaurer
     */
    function restoreFormData(container, formData) {
        container.querySelectorAll('form').forEach(form => {
            const networkInput = form.querySelector('input[name="network"]');
            if (!networkInput) return;
            
            const network = networkInput.value;
            if (!formData[network]) return;
            
            form.querySelectorAll('textarea, input').forEach(field => {
                if (field.name && formData[network][field.name] !== undefined) {
                    field.value = formData[network][field.name];
                }
            });
        });
    }
    
    /**
     * Valide et soumet tous les formulaires
     * @param {NodeList|Array} forms - Formulaires à valider et soumettre
     * @param {Object} options - Options de configuration
     * @returns {Promise<boolean>} Succès de la soumission
     */
    async function validateAndSubmitForms(forms, options = {}) {
        const { 
            spinner, 
            onSuccess, 
            onError, 
            modifiedImages = null,
            modalId = null,
            imageFile = null  // Pour modal-post-image
        } = options;
        
        let allValid = true;
        const invalidFields = [];
        
        // Validation
        forms.forEach(form => {
            if (!form.checkValidity()) {
                allValid = false;
                
                form.querySelectorAll(':invalid').forEach(field => {
                    field.classList.add('is-invalid');
                    invalidFields.push(field);
                    
                    // Cleanup automatique pour éviter les memory leaks
                    field.addEventListener('input', function removeInvalid() {
                        field.classList.remove('is-invalid');
                        field.removeEventListener('input', removeInvalid);
                    }, { once: true });
                });
            }
        });
        
        if (!allValid) {
            console.warn(`${invalidFields.length} champ(s) invalide(s)`);
            return false;
        }
        
        // Afficher le spinner si fourni
        if (spinner) spinner.style.display = 'block';
        
        try {
            const promises = [];
            
            forms.forEach(form => {
                const formData = new FormData(form);
                const network = form.querySelector('input[name="network"]')?.value;
                
                // Cas 1: Image modifiée dans modal-handler ou import-link-handler
                if (modifiedImages && modalId && network) {
                    if (modifiedImages[modalId] && modifiedImages[modalId][network]) {
                        const imageFileToUpload = modifiedImages[modalId][network].file;
                        formData.append('imageFile', imageFileToUpload);
                    }
                } else if (modifiedImages && network && !modalId) {
                    // Pour import-link-handler (pas de modalId)
                    if (modifiedImages[network]) {
                        const imageFileToUpload = modifiedImages[network].file;
                        formData.append('imageFile', imageFileToUpload);
                    }
                }
                
                // Cas 2: Image unique pour tous les formulaires (modal-post-image)
                if (imageFile) {
                    formData.append('imageFile', imageFile);
                }
                
                const promise = fetch(form.action, {
                    method: form.method,
                    body: formData
                });
                
                promises.push(promise);
            });
            
            const responses = await Promise.all(promises);
            const allSuccess = responses.every(r => r.ok);
            
            if (allSuccess) {
                if (onSuccess) onSuccess(responses);
                return true;
            } else {
                throw new Error('Certaines soumissions ont échoué');
            }
        } catch (error) {
            console.error('Erreur lors des soumissions:', error);
            if (onError) onError(error);
            return false;
        } finally {
            if (spinner) spinner.style.display = 'none';
        }
    }
    
    /**
     * Upload et prévisualisation d'une image
     * @param {HTMLInputElement} fileInput - Input file
     * @param {HTMLImageElement} previewElement - Element img pour la preview
     * @returns {Promise<Object>} Objet {file, url}
     */
    async function uploadImageFile(fileInput, previewElement) {
        if (!fileInput.files || !fileInput.files[0]) {
            throw new Error('Aucun fichier sélectionné');
        }
        
        const file = fileInput.files[0];
        
        // Validation du type
        if (!file.type.startsWith('image/')) {
            throw new Error('Le fichier doit être une image');
        }
        
        // Validation de la taille (5MB max)
        if (file.size > 5 * 1024 * 1024) {
            throw new Error('Image trop volumineuse (max 5MB)');
        }
        
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            
            reader.onload = (e) => {
                const dataUrl = e.target.result;
                
                // Mettre à jour la preview si fournie
                if (previewElement) {
                    previewElement.src = dataUrl;
                }
                
                resolve({ file, url: dataUrl });
            };
            
            reader.onerror = () => {
                reject(new Error('Erreur lors de la lecture du fichier'));
            };
            
            reader.readAsDataURL(file);
        });
    }
    
    /**
     * Attache les event listeners pour l'upload d'image
     * @param {string} network - Nom du réseau
     * @param {string} uniqueId - ID unique (modalId ou autre)
     * @param {Object} modifiedImages - Objet pour stocker les images modifiées
     */
    function attachImageUploadHandlers(network, uniqueId, modifiedImages) {
        const uploadBtn = document.getElementById(`modifyImageBtn_${network}_${uniqueId}`);
        const fileInput = document.getElementById(`modifyImageFormFile_${network}_${uniqueId}`);
        const previewImg = document.getElementById(`previewImage_${network}_${uniqueId}`);
        
        if (!uploadBtn || !fileInput || !previewImg) {
            console.warn(`Éléments d'upload manquants pour ${network}_${uniqueId}`);
            return;
        }
        
        uploadBtn.disabled = true;
        
        // Activer le bouton upload si un fichier est sélectionné
        fileInput.addEventListener('change', () => {
            uploadBtn.disabled = fileInput.files.length === 0;
        });
        
        // Gérer l'upload
        uploadBtn.addEventListener('click', async () => {
            try {
                const imageData = await uploadImageFile(fileInput, previewImg);
                
                // Stocker l'image modifiée
                if (!modifiedImages[uniqueId]) {
                    modifiedImages[uniqueId] = {};
                }
                modifiedImages[uniqueId][network] = imageData;
                
                console.log(`Image uploadée pour ${network}_${uniqueId}`);
            } catch (error) {
                console.error('Erreur upload:', error);
                alert(error.message);
            }
        });
    }
    
    /**
     * Échappe les caractères HTML pour éviter les injections XSS
     * @param {string} text - Texte à échapper
     * @returns {string} Texte échappé
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Tronque un texte à une longueur donnée
     * @param {string} text - Texte à tronquer
     * @param {number} maxLength - Longueur maximum
     * @returns {string} Texte tronqué
     */
    function truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
    
    // API publique
    return {
        saveFormData,
        restoreFormData,
        validateAndSubmitForms,
        uploadImageFile,
        attachImageUploadHandlers,
        escapeHtml,
        truncateText
    };
})();
