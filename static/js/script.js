$(document).ready(function() {
    // --- Splash Screen & Main Container ---
    $('#getStartedBtn').on('click', function() {
        $('#splashScreen').fadeOut(400, function() {
            $('#main-flex-container').fadeIn(400);
        });
    });

    // --- Sidebar ---
    const sidebar = $('#sidebar-history');
    const translatorApp = $('#translatorApp');
    const toggleSidebarBtn = $('#toggleSidebarBtn');
    const toggleSidebarIcon = $('#toggleSidebarIcon');
    let sidebarVisible = localStorage.getItem('sidebarVisible') === 'true';

    function setSidebarVisible(visible) {
        if (visible) {
            sidebar.show();
            toggleSidebarIcon.text('«');
            translatorApp.removeClass('sidebar-closed');
        } else {
            sidebar.hide();
            toggleSidebarIcon.text('»');
            translatorApp.addClass('sidebar-closed');
        }
        localStorage.setItem('sidebarVisible', visible.toString());
    }

    setSidebarVisible(sidebarVisible);
    toggleSidebarBtn.on('click', () => setSidebarVisible(!sidebarVisible));

    // --- Translation ---
    $('#translateBtn').on('click', function() {
        const text = $('#inputText').val();
        const langFrom = $('#langFrom').val();
        const langTo = $('#langTo').val();
        const enableTransliteration = $('#transliterateCheckbox').is(':checked');
        const $btn = $(this);

        if (!text.trim()) {
            showError('Please enter text to translate.');
            return;
        }

        $btn.prop('disabled', true).text('Translating...');

        $.ajax({
            url: '/translate',
            method: 'POST',
            data: {
                text: text,
                lang_from: langFrom,
                lang_to: langTo,
                transliterate: enableTransliteration // This is the corrected part
            },
            success: function(response) {
                if (response.translated_text) {
                    $('#outputText').val(response.translated_text);
                    fetchHistory();
                } else {
                    showError(response.error || 'An unknown error occurred.');
                }
            },
            error: function() {
                showError('An error occurred while communicating with the server.');
            },
            complete: function() {
                $btn.prop('disabled', false).text('Translate');
            }
        });
    });

    // --- Transliteration ---
    $('#transliterateBtn').on('click', function() {
        const text = $('#inputText').val();
        const langTo = $('#langTo').val(); // Transliterate to the target language
        const $btn = $(this);

        if (!text.trim()) {
            showError('Please enter text to transliterate.');
            return;
        }

        $btn.prop('disabled', true).text('Transliterating...');

        $.ajax({
            url: '/transliterate',
            method: 'POST',
            data: {
                text: text,
                lang_to: langTo
            },
            success: function(response) {
                if (response.transliterated_text) {
                    $('#inputText').val(response.transliterated_text);
                } else {
                    showError(response.error || 'An unknown error occurred.');
                }
            },
            error: function() {
                showError('An error occurred while communicating with the server.');
            },
            complete: function() {
                $btn.prop('disabled', false).text('Transliterate');
            }
        });
    });

    // --- History ---
    function fetchHistory() {
        $.get('/history', function(data) {
            const historyList = $('#translation-history-list');
            historyList.empty();
            if (data && data.length > 0) {
                data.forEach(function(item) {
                    const listItem = `
                        <li class="list-group-item">
                            <span style="font-weight:600; color:#6366f1;">${item.source_lang_name || item.source_lang.toUpperCase()}</span> →
                            <span style="font-weight:600; color:#f472b6;">${item.target_lang_name || item.target_lang.toUpperCase()}</span><br>
                            <span style="color:#3730a3;">${item.source_text}</span> →
                            <span style="color:#27ae60;">${item.translated_text}</span><br>
                            <span style="font-size:0.85em; color:#888;">${new Date(item.timestamp).toLocaleString()}</span>
                        </li>`;
                    historyList.append(listItem);
                });
            } else {
                historyList.append('<li class="list-group-item">No translation history found.</li>');
            }
        });
    }

    // --- Dark Mode ---
    const darkModeToggle = $('#darkModeToggle');
    const darkModeIcon = $('#darkModeIcon');
    let darkMode = localStorage.getItem('darkMode') === 'true';

    function setDarkMode(enabled) {
        $('body').toggleClass('dark-mode', enabled);
        darkModeIcon.text(enabled ? '☀️' : '🌙');
        localStorage.setItem('darkMode', enabled.toString());
    }

    setDarkMode(darkMode);
    darkModeToggle.on('click', () => setDarkMode(!$('body').hasClass('dark-mode')));

    // --- Utility Functions ---
    $('#clearAllBtn').on('click', function() {
        $('#inputText, #outputText').val('');
    });

    function showError(message) {
        // Simple alert for now, can be styled later
        alert(message);
    }
    
    // Initial Load
    fetchHistory();

    // --- Swap Languages Button ---
    $('#swapLangBtn').on('click', function() {
        // Swap the selected languages
        const langFromSelect = $('#langFrom');
        const langToSelect = $('#langTo');
        const tempLang = langFromSelect.val();
        langFromSelect.val(langToSelect.val());
        langToSelect.val(tempLang);

        // Swap the input and output text areas
        const inputText = $('#inputText').val();
        const outputText = $('#outputText').val();
        $('#inputText').val(outputText);
        $('#outputText').val(inputText);
    });
});
