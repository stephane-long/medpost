// character-counter.js

document.addEventListener('DOMContentLoaded', function() {
    // Sélectionne tous les textareas
    const textareas = document.querySelectorAll('textarea[id^="content"]');
    
    textareas.forEach(function(textarea) {
        textarea.addEventListener('input', function() {
            // Récupère l'ID du compteur correspondant
            const helpId = 'contentHelp' + this.id.substring(7);  // Enlève 'content' du début
            const counter = document.getElementById(helpId);
            
            if (counter) {
                counter.textContent = this.value.length + ' caractères';
            }
        });
        
        // Initialise le compteur
        const helpId = 'contentHelp' + textarea.id.substring(7);
        const counter = document.getElementById(helpId);
        if (counter) {
            counter.textContent = textarea.value.length + ' caractères';
        }
    });
});
