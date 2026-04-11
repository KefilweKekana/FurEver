/**
 * FurEver Kennel AI Chatbot + Internal Messaging + Voice/Video Calling + TTS
 * Tabs: AI Assistant (shelter queries), Messages (user-to-user DMs)
 * Features: Animal photo cards, WebRTC calling, Speech-to-Text, Text-to-Speech
 */
(function() {
    if (!frappe.session || frappe.session.user === 'Guest') return;

    var chatOpen = false;
    var activeTab = 'ai';
    var dmUser = null;
    var dmUserName = '';
    var dmPollTimer = null;
    var msgPollTimer = null;
    var unreadCount = 0;

    // WebRTC call state
    var callState = null;
    var ringtoneInterval = null;

    // TTS state
    var speechSynth = window.speechSynthesis || null;
    var autoSpeak = false; // Only auto-speak when voice mode is explicitly activated
    var isSpeaking = false;
    var lastMsgWasVoice = false; // Track if last user message was via voice input

    // STT state
    var recognition = null;
    var isListening = false;

    // Wake word state
    var WAKE_NAME = 'scout';
    var WAKE_PHRASES = ['hey scout', 'hi scout', 'ok scout', 'okay scout', 'yo scout'];
    var wakeRecognition = null;
    var wakeListening = false;

    // Chat history persistence
    var CHAT_STORAGE_KEY = 'km_chat_history_' + (frappe.session.user || 'anon');
    var CHAT_MAX_MESSAGES = 100;

    $(document).ready(function() { build_chat_ui(); setup_call_listeners(); start_wake_word_listener(); });

    /* ========== DOG SVG ========== */
    var dogSVG = '<svg class="km-dog-svg" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">'
        + '<path class="km-dog-tail" d="M10 16 Q4 8, 8 4"/>'
        + '<ellipse class="km-dog-body" cx="24" cy="28" rx="14" ry="12"/>'
        + '<circle class="km-dog-body" cx="36" cy="18" r="10"/>'
        + '<ellipse class="km-dog-ear" cx="30" cy="9" rx="4" ry="6" transform="rotate(-15 30 9)"/>'
        + '<ellipse class="km-dog-ear" cx="42" cy="11" rx="4" ry="6" transform="rotate(15 42 11)"/>'
        + '<circle class="km-dog-eye" cx="33" cy="17" r="1.8"/>'
        + '<circle class="km-dog-eye" cx="40" cy="17" r="1.8"/>'
        + '<ellipse class="km-dog-nose" cx="37" cy="21" rx="2.2" ry="1.6"/>'
        + '<rect class="km-dog-tongue" x="35.5" y="23" width="3" height="4" rx="1.5" transform-origin="37 23"/>'
        + '<rect class="km-dog-body" x="15" y="36" width="4" height="8" rx="2"/>'
        + '<rect class="km-dog-body" x="23" y="36" width="4" height="8" rx="2"/>'
        + '<rect class="km-dog-body" x="29" y="36" width="4" height="8" rx="2"/>'
        + '</svg>';

    /* ========== BUILD UI ========== */
    function build_chat_ui() {
        var fab = $('<button class="km-chat-fab" title="Hey Scout — your AI assistant">' + dogSVG + '<span class="km-fab-badge"></span></button>');

        var win = $([
        '<div class="km-chat-window" id="km-chat-window">',
            '<div class="km-chat-header">',
                '<div class="km-chat-avatar"><i class="fa fa-paw"></i></div>',
                '<div class="km-chat-hdr-info">',
                    '<h4>Scout</h4>',
                    '<span>AI Assistant &amp; Team Chat</span>',
                '</div>',
                '<button class="km-auto-speak-btn" id="km-auto-speak-btn" title="Toggle auto-speak"><i class="fa fa-volume-up"></i></button>',
                '<button class="km-clear-chat-btn" id="km-clear-chat-btn" title="Clear chat history"><i class="fa fa-trash-o"></i></button>',
                '<button class="km-chat-close"><i class="fa fa-times"></i></button>',
            '</div>',
            '<div class="km-chat-tabs">',
                '<button class="km-chat-tab active" data-tab="ai"><i class="fa fa-magic"></i> Assistant</button>',
                '<button class="km-chat-tab" data-tab="messages"><i class="fa fa-comments"></i> Messages <span class="km-tab-badge" id="km-msg-badge"></span></button>',
            '</div>',
            '<div class="km-tab-panel active" id="km-panel-ai">',
                '<div class="km-chat-quick">',
                    '<button class="km-chat-chip" data-q="How many animals are in the shelter?">Animals</button>',
                    '<button class="km-chat-chip" data-q="Show today\'s vet appointments">Vet today</button>',
                    '<button class="km-chat-chip" data-q="What is the kennel occupancy?">Occupancy</button>',
                    '<button class="km-chat-chip" data-q="Any pending adoption applications?">Adoptions</button>',
                    '<button class="km-chat-chip" data-q="Show recent admissions">Intake</button>',
                    '<button class="km-chat-chip" data-q="Which animals have been waiting longest?">Long stays</button>',
                    '<button class="km-chat-chip" data-q="Are any kennels full?">Full kennels</button>',
                    '<button class="km-chat-chip km-chip-special" data-q="__admit_dog">🐕 Admit Dog</button>',
                    '<button class="km-chat-chip km-chip-special" data-q="__client_info">📋 Client Info</button>',
                    '<button class="km-chat-chip km-chip-special km-chip-doc" data-q="__scan_doc">📄 Scan Document</button>',
                    '<button class="km-chat-chip km-chip-wake" data-q="__voice_mode">🎙️ Voice Mode</button>',
                '</div>',
                '<div class="km-chat-messages" id="km-ai-messages"></div>',
                '<div class="km-vision-preview" id="km-vision-preview" style="display:none;">',
                    '<img id="km-preview-img" />',
                    '<video id="km-camera-feed" autoplay playsinline style="display:none;"></video>',
                    '<canvas id="km-camera-canvas" style="display:none;"></canvas>',
                    '<div class="km-preview-actions">',
                        '<button class="km-preview-btn" id="km-camera-snap" style="display:none;" title="Take photo"><i class="fa fa-camera"></i> Snap</button>',
                        '<button class="km-preview-btn km-preview-cancel" id="km-preview-cancel"><i class="fa fa-times"></i></button>',
                        '<button class="km-preview-btn km-preview-send" id="km-preview-send"><i class="fa fa-paper-plane"></i> Analyze</button>',
                    '</div>',
                '</div>',
                '<div class="km-chat-input-area">',
                    '<button class="km-mic-btn" id="km-mic-btn" title="Voice input"><i class="fa fa-microphone"></i></button>',
                    '<button class="km-media-btn" id="km-camera-btn" title="Camera - identify breed"><i class="fa fa-camera"></i></button>',
                    '<button class="km-media-btn" id="km-upload-btn" title="Upload image"><i class="fa fa-image"></i></button>',
                    '<button class="km-media-btn km-doc-btn" id="km-doc-upload-btn" title="Scan document / form"><i class="fa fa-file-text"></i></button>',
                    '<input type="file" id="km-file-input" accept="image/*" style="display:none;" />',
                    '<input type="file" id="km-doc-file-input" accept="image/*,.pdf" style="display:none;" />',
                    '<input class="km-chat-input" id="km-ai-input" placeholder="Ask about the shelter..." autocomplete="off" />',
                    '<button class="km-chat-send" id="km-ai-send"><i class="fa fa-paper-plane"></i></button>',
                '</div>',
            '</div>',
            '<div class="km-tab-panel" id="km-panel-messages">',
                '<div id="km-msg-list-view">',
                    '<div class="km-user-search">',
                        '<input type="text" placeholder="Search users..." id="km-user-search-input" />',
                    '</div>',
                    '<div class="km-user-list" id="km-user-list">',
                        '<div class="km-empty-state"><i class="fa fa-comments"></i><p>Loading team...</p></div>',
                    '</div>',
                '</div>',
                '<div id="km-dm-view" style="display:none;flex-direction:column;flex:1;overflow:hidden;">',
                    '<div class="km-dm-header">',
                        '<button class="km-dm-back"><i class="fa fa-arrow-left"></i></button>',
                        '<div class="km-user-avatar km-dm-avatar"></div>',
                        '<div style="flex:1;min-width:0;">',
                            '<div class="km-dm-name"></div>',
                            '<div class="km-dm-status">Shelter staff</div>',
                        '</div>',
                        '<div class="km-dm-call-btns">',
                            '<button class="km-call-btn km-voice-call-btn" title="Voice call"><i class="fa fa-phone"></i></button>',
                            '<button class="km-call-btn km-video-call-btn" title="Video call"><i class="fa fa-video-camera"></i></button>',
                        '</div>',
                    '</div>',
                    '<div class="km-chat-messages" id="km-dm-messages"></div>',
                    '<div class="km-chat-input-area">',
                        '<input class="km-chat-input" id="km-dm-input" placeholder="Type a message..." autocomplete="off" />',
                        '<button class="km-chat-send" id="km-dm-send"><i class="fa fa-paper-plane"></i></button>',
                    '</div>',
                '</div>',
            '</div>',
            '<div class="km-chat-footer">Scout — FurEver Kennel Management <span class="km-wake-status" id="km-wake-status" title="Say \"Hey Scout\" to activate">🎤</span></div>',
        '</div>'
        ].join('\n'));

        // Call overlay
        var callOverlay = $([
        '<div class="km-call-overlay" id="km-call-overlay">',
            '<div class="km-call-modal">',
                '<div class="km-call-status" id="km-call-status">Calling...</div>',
                '<div class="km-call-peer-name" id="km-call-peer-name"></div>',
                '<div class="km-call-type-icon" id="km-call-type-icon"><i class="fa fa-phone"></i></div>',
                '<div class="km-call-timer" id="km-call-timer" style="display:none;">00:00</div>',
                '<div class="km-call-video-container" id="km-call-video-container" style="display:none;">',
                    '<video id="km-remote-video" autoplay playsinline></video>',
                    '<video id="km-local-video" autoplay playsinline muted></video>',
                '</div>',
                '<audio id="km-remote-audio" autoplay></audio>',
                '<div class="km-call-actions">',
                    '<button class="km-call-action-btn km-call-mute" id="km-call-mute" title="Mute"><i class="fa fa-microphone"></i></button>',
                    '<button class="km-call-action-btn km-call-end" id="km-call-end" title="End call"><i class="fa fa-phone"></i></button>',
                    '<button class="km-call-action-btn km-call-accept" id="km-call-accept" title="Accept" style="display:none;"><i class="fa fa-phone"></i></button>',
                    '<button class="km-call-action-btn km-call-reject" id="km-call-reject" title="Reject" style="display:none;"><i class="fa fa-times"></i></button>',
                '</div>',
            '</div>',
        '</div>'
        ].join('\n'));

        $('body').append(fab).append(win).append(callOverlay);

        // AI welcome — dog face orb + suggestion cards
        var orbHtml = '<div class="km-scout-orb">'
            + '<div class="km-orb-container">'
            + '<div class="km-orb-ring km-orb-ring-1"></div>'
            + '<div class="km-orb-ring km-orb-ring-2"></div>'
            + '<div class="km-orb-ring km-orb-ring-3"></div>'
            + '<div class="km-dog-face">'
            +   '<div class="km-dog-face-ear km-dog-face-ear-l"></div>'
            +   '<div class="km-dog-face-ear km-dog-face-ear-r"></div>'
            +   '<div class="km-dog-face-eye km-dog-face-eye-l"><div class="km-dog-face-pupil"></div></div>'
            +   '<div class="km-dog-face-eye km-dog-face-eye-r"><div class="km-dog-face-pupil"></div></div>'
            +   '<div class="km-dog-face-nose"></div>'
            +   '<div class="km-dog-face-mouth"></div>'
            + '</div>'
            + '<div class="km-orb-particle km-orb-p1"></div>'
            + '<div class="km-orb-particle km-orb-p2"></div>'
            + '<div class="km-orb-particle km-orb-p3"></div>'
            + '<div class="km-orb-sparkle">✦</div>'
            + '</div>'
            + '<div class="km-scout-welcome-text">Hello! 🐾<br>How can I help you today?</div>'
            + '<div class="km-scout-welcome-sub">Ask anything about your shelter</div>'
            + '</div>';
        var cardsHtml = '<div class="km-suggestion-cards">'
            + '<div class="km-suggestion-card km-sc-animals" data-q="How many animals are in the shelter?">'
            + '<div class="km-suggestion-card-header"><div class="km-sc-icon"><i class="fa fa-paw"></i></div><div class="km-sc-label">Animals</div></div>'
            + '<div class="km-suggestion-card-desc">View shelter stats, kennels & long stays</div></div>'
            + '<div class="km-suggestion-card km-sc-vet" data-q="Show today\'s vet appointments">'
            + '<div class="km-suggestion-card-header"><div class="km-sc-icon"><i class="fa fa-heartbeat"></i></div><div class="km-sc-label">Vet Today</div></div>'
            + '<div class="km-suggestion-card-desc">Check appointments & medical holds</div></div>'
            + '<div class="km-suggestion-card km-sc-admit" data-q="__admit_dog">'
            + '<div class="km-suggestion-card-header"><div class="km-sc-icon"><i class="fa fa-plus-circle"></i></div><div class="km-sc-label">Admit Dog</div></div>'
            + '<div class="km-suggestion-card-desc">Step-by-step intake assistant</div></div>'
            + '<div class="km-suggestion-card km-sc-voice" data-q="__voice_mode">'
            + '<div class="km-suggestion-card-header"><div class="km-sc-icon"><i class="fa fa-microphone"></i></div><div class="km-sc-label">Voice Mode</div></div>'
            + '<div class="km-suggestion-card-desc">Talk to Scout hands-free</div></div>'
            + '</div>';
        $('#km-ai-messages').append(orbHtml).append(cardsHtml);

        // Restore chat history from localStorage
        restore_chat_history();

        // Suggestion card click handlers
        $('#km-ai-messages').on('click', '.km-suggestion-card', function() {
            var q = $(this).data('q');
            if (!q) return;
            if (q === '__admit_dog') { start_admission_flow(); return; }
            if (q === '__client_info') { start_client_info_flow(); return; }
            if (q === '__scan_doc') { start_document_scan(); return; }
            if (q === '__voice_mode') { activate_voice_mode(); return; }
            send_ai_message(q);
        });

        // Events
        fab.on('click', toggle_chat);
        win.find('.km-chat-close').on('click', toggle_chat);
        win.find('.km-chat-tab').on('click', function() { switch_tab($(this).data('tab')); });

        // AI events
        win.find('.km-chat-chip').on('click', function() {
            var q = $(this).data('q');
            if (q === '__admit_dog') { start_admission_flow(); return; }
            if (q === '__client_info') { start_client_info_flow(); return; }
            if (q === '__scan_doc') { start_document_scan(); return; }
            if (q === '__voice_mode') { activate_voice_mode(); return; }
            send_ai_message(q);
        });
        win.find('#km-ai-send').on('click', function() {
            var msg = $('#km-ai-input').val().trim();
            if (msg) send_ai_message(msg);
        });
        win.find('#km-ai-input').on('keypress', function(e) {
            if (e.which === 13) { var msg = $(this).val().trim(); if (msg) send_ai_message(msg); }
        });

        // Mic button
        win.find('#km-mic-btn').on('click', toggle_stt);
        win.find('#km-auto-speak-btn').on('click', toggle_auto_speak);
        win.find('#km-clear-chat-btn').on('click', clear_chat_history);

        // Camera & upload events
        win.find('#km-camera-btn').on('click', open_camera);
        win.find('#km-upload-btn').on('click', function() { $('#km-file-input').click(); });
        win.find('#km-file-input').on('change', handle_file_upload);
        win.find('#km-preview-cancel').on('click', close_preview);
        win.find('#km-preview-send').on('click', send_vision_query);
        win.find('#km-camera-snap').on('click', snap_camera);
        win.find('#km-doc-upload-btn').on('click', function() { docScanMode = true; $('#km-doc-file-input').click(); });
        win.find('#km-doc-file-input').on('change', handle_doc_upload);

        // DM events
        win.find('#km-dm-send').on('click', function() {
            var msg = $('#km-dm-input').val().trim();
            if (msg && dmUser) send_dm(msg);
        });
        win.find('#km-dm-input').on('keypress', function(e) {
            if (e.which === 13) { var msg = $(this).val().trim(); if (msg && dmUser) send_dm(msg); }
        });
        win.find('.km-dm-back').on('click', close_dm);

        // Call buttons in DM
        win.find('.km-voice-call-btn').on('click', function() { if (dmUser) start_call(dmUser, dmUserName, 'voice'); });
        win.find('.km-video-call-btn').on('click', function() { if (dmUser) start_call(dmUser, dmUserName, 'video'); });

        // Call overlay actions
        $('#km-call-end').on('click', end_call);
        $('#km-call-accept').on('click', accept_call);
        $('#km-call-reject').on('click', reject_call);
        $('#km-call-mute').on('click', toggle_mute);

        // User search
        win.find('#km-user-search-input').on('input', function() {
            var q = $(this).val().trim().toLowerCase();
            $('#km-user-list .km-user-item').each(function() {
                var name = $(this).data('fullname').toLowerCase();
                $(this).toggle(name.indexOf(q) !== -1);
            });
        });

        check_unread();
        msgPollTimer = setInterval(check_unread, 15000);
    }

    /* ========== TABS ========== */
    function switch_tab(tab) {
        activeTab = tab;
        $('.km-chat-tab').removeClass('active');
        $('.km-chat-tab[data-tab="' + tab + '"]').addClass('active');
        $('.km-tab-panel').removeClass('active');
        $('#km-panel-' + tab).addClass('active');
        if (tab === 'messages') load_user_list();
    }

    function toggle_chat() {
        chatOpen = !chatOpen;
        $('#km-chat-window').toggleClass('open', chatOpen);
        if (chatOpen) {
            if (activeTab === 'ai') setTimeout(function() { $('#km-ai-input').focus(); }, 200);
            else load_user_list();
        }
    }

    /* ========== VOICE MODE TOGGLE ========== */
    function toggle_auto_speak() {
        autoSpeak = !autoSpeak;
        $('#km-auto-speak-btn i').toggleClass('fa-volume-up', autoSpeak).toggleClass('fa-volume-off', !autoSpeak);
        $('#km-auto-speak-btn').toggleClass('km-auto-speak-off', !autoSpeak);
        if (autoSpeak) {
            frappe.show_alert({message: 'Voice Mode ON — Scout will speak responses 🔊\nClick 🎤 or say "Hey Scout" to talk', indicator: 'green'});
        } else {
            frappe.show_alert({message: 'Voice Mode OFF 🔇', indicator: 'orange'});
            stop_speaking();
            if (isListening) stop_stt();
        }
    }

    /* ========== VOICE MODE ========== */
    function activate_voice_mode() {
        if (!chatOpen) toggle_chat();
        autoSpeak = true;
        $('#km-auto-speak-btn i').removeClass('fa-volume-off').addClass('fa-volume-up');
        $('#km-auto-speak-btn').removeClass('km-auto-speak-off');
        add_bot_message("🎙️ **Voice Mode Active!**\n\nClick the 🎤 mic button or say **\"Hey Scout\"** to speak to me. I'll respond with voice.\n\nToggle the 🔊 icon to exit voice mode.", null, true);
    }

    /* ========== AI ASSISTANT ========== */
    function add_bot_message(text, animals, skipSpeak, skipSave) {
        var time = frappe.datetime.now_time().substring(0, 5);
        var msgHtml = '<div class="km-msg km-msg-bot">'
            + format_bot_text(text)
            + '<div class="km-msg-time">' + time
            + ' <button class="km-tts-btn" title="Listen"><i class="fa fa-volume-up"></i></button>'
            + '</div></div>';
        $('#km-ai-messages').append(msgHtml);

        // Save to history
        if (!skipSave) save_chat_message('bot', text, animals || null, time);

        // Animal photo cards
        if (animals && animals.length) {
            var cardsHtml = '<div class="km-animal-cards">';
            animals.forEach(function(a) {
                var photoHtml = a.photo
                    ? '<img src="' + a.photo + '" alt="' + frappe.utils.escape_html(a.animal_name) + '" class="km-animal-card-photo" />'
                    : '<div class="km-animal-card-nophoto"><i class="fa fa-paw"></i></div>';
                var statusCls = 'km-st-' + (a.status || '').toLowerCase().replace(/[^a-z]/g, '');
                cardsHtml += '<div class="km-animal-card" data-animal="' + a.name + '">'
                    + photoHtml
                    + '<div class="km-animal-card-body">'
                    + '<div class="km-animal-card-name">' + frappe.utils.escape_html(a.animal_name) + '</div>'
                    + '<div class="km-animal-card-detail">'
                    + frappe.utils.escape_html(a.species || '')
                    + (a.breed ? ' / ' + frappe.utils.escape_html(a.breed) : '')
                    + (a.gender ? ' &middot; ' + frappe.utils.escape_html(a.gender) : '')
                    + '</div>'
                    + '<span class="km-animal-card-badge ' + statusCls + '">' + frappe.utils.escape_html(a.status || '') + '</span>'
                    + (a.kennel ? '<div class="km-animal-card-kennel"><i class="fa fa-home"></i> ' + frappe.utils.escape_html(a.kennel) + '</div>' : '')
                    + '</div></div>';
            });
            cardsHtml += '</div>';
            $('#km-ai-messages').append(cardsHtml);

            // Click to open animal record
            $('#km-ai-messages .km-animal-card').last().parent().find('.km-animal-card').on('click', function() {
                var id = $(this).data('animal');
                if (id) window.open('/app/animal/' + id, '_blank');
            });
        }

        // TTS button binding
        $('#km-ai-messages .km-tts-btn').last().on('click', function(e) {
            e.stopPropagation();
            speak_text(text);
        });

        scroll_el('km-ai-messages');

        // Auto-speak only in voice mode (autoSpeak) or if last message was via voice
        if ((autoSpeak || lastMsgWasVoice) && !skipSpeak) {
            var isVoiceConvo = autoSpeak;
            lastMsgWasVoice = false;
            // In voice conversation mode, use browser TTS only for zero latency
            speak_text(text, isVoiceConvo);
        }
    }

    function add_user_ai_message(text, skipSave) {
        var time = frappe.datetime.now_time().substring(0, 5);
        $('#km-ai-messages').append(
            '<div class="km-msg km-msg-user">' + frappe.utils.escape_html(text) + '<div class="km-msg-time">' + time + '</div></div>'
        );
        scroll_el('km-ai-messages');

        // Save to history
        if (!skipSave) save_chat_message('user', text, null, time);
    }

    function send_ai_message(text) {
        add_user_ai_message(text);
        $('#km-ai-input').val('');

        // Check if we're in a document clarification flow
        if (docClarifyState && handle_clarification_answer(text)) {
            return;
        }

        // Check if we're in an admission or client info flow
        if (admissionState && handle_admission_step(text)) {
            return;
        }

        $('#km-ai-send').prop('disabled', true);
        show_typing('km-ai-messages');

        var isVoice = autoSpeak || lastMsgWasVoice;

        // Build conversation history from localStorage for multi-turn context
        var chatHistory = [];
        try {
            var stored = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
            // Send last 20 messages as conversation context
            var recent = stored.slice(-20);
            recent.forEach(function(m) {
                chatHistory.push({
                    role: m.role === 'user' ? 'user' : 'assistant',
                    content: m.text
                });
            });
        } catch(e) {}

        frappe.call({
            method: 'kennel_management.api.chatbot_query',
            args: {
                message: text,
                is_voice: isVoice ? 1 : 0,
                conversation_history: JSON.stringify(chatHistory)
            },
            callback: function(r) {
                hide_typing();
                $('#km-ai-send').prop('disabled', false);
                if (r.message) {
                    add_bot_message(r.message.reply, r.message.animals || null);
                    if (r.message.actions && r.message.actions.length) render_actions(r.message.actions);
                } else {
                    add_bot_message("Sorry, I couldn't process that. Try again.");
                }
            },
            error: function() {
                hide_typing();
                $('#km-ai-send').prop('disabled', false);
                add_bot_message("Something went wrong. Please try again.");
            }
        });
    }

    /* ========== VISION / CAMERA / IMAGE UPLOAD ========== */
    var pendingImageData = null;
    var cameraStream = null;

    function open_camera() {
        navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: 640, height: 480 } })
            .then(function(stream) {
                cameraStream = stream;
                var video = document.getElementById('km-camera-feed');
                video.srcObject = stream;
                video.style.display = 'block';
                $('#km-preview-img').hide();
                $('#km-camera-snap').hide();
                // Show analyze button directly — live video mode
                $('#km-preview-send').show().html('<i class="fa fa-search"></i> Analyze Live');
                $('#km-vision-preview').show();
            })
            .catch(function(err) {
                frappe.show_alert({message: 'Camera access denied: ' + err.message, indicator: 'red'});
            });
    }

    function snap_camera() {
        // Capture frame from live feed for analysis
        var video = document.getElementById('km-camera-feed');
        var canvas = document.getElementById('km-camera-canvas');
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        canvas.getContext('2d').drawImage(video, 0, 0);
        return canvas.toDataURL('image/jpeg', 0.85);
    }

    function handle_file_upload(e) {
        var file = e.target.files[0];
        if (!file) return;
        if (!file.type.startsWith('image/')) {
            frappe.show_alert({message: 'Please select an image file', indicator: 'orange'});
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            frappe.show_alert({message: 'Image must be under 10MB', indicator: 'orange'});
            return;
        }
        var reader = new FileReader();
        reader.onload = function(ev) {
            pendingImageData = ev.target.result;
            $('#km-camera-feed').hide();
            $('#km-camera-snap').hide();
            $('#km-preview-img').attr('src', pendingImageData).show();
            $('#km-preview-send').show();
            $('#km-vision-preview').show();
        };
        reader.readAsDataURL(file);
        $('#km-file-input').val('');
    }

    function close_preview() {
        stop_camera_stream();
        pendingImageData = null;
        docScanMode = false;
        $('#km-vision-preview').hide();
        $('#km-preview-img').attr('src', '').hide();
        $('#km-camera-feed').hide();
        $('#km-camera-snap').hide();
        $('#km-preview-send').html('<i class="fa fa-paper-plane"></i> Analyze');
    }

    function stop_camera_stream() {
        if (cameraStream) {
            cameraStream.getTracks().forEach(function(t) { t.stop(); });
            cameraStream = null;
        }
    }

    function send_vision_query() {
        // For live camera, capture a frame first
        if (cameraStream && !pendingImageData) {
            pendingImageData = snap_camera();
        }
        if (!pendingImageData) return;
        // Route to document scanner if in doc mode
        if (docScanMode) { send_document_scan(); return; }
        var imageData = pendingImageData;
        var userPrompt = $('#km-ai-input').val().trim() || 'Identify this dog\'s breed, approximate age, and health observations. Also suggest a name.';
        close_preview();

        // Show thumbnail in chat
        var time = frappe.datetime.now_time().substring(0, 5);
        $('#km-ai-messages').append(
            '<div class="km-msg km-msg-user">'
            + '<img src="' + imageData + '" class="km-chat-img-thumb" />'
            + '<div class="km-vision-prompt">' + frappe.utils.escape_html(userPrompt) + '</div>'
            + '<div class="km-msg-time">' + time + '</div></div>'
        );
        scroll_el('km-ai-messages');
        show_typing('km-ai-messages');
        $('#km-ai-send').prop('disabled', true);

        frappe.call({
            method: 'kennel_management.api.chatbot_vision_query',
            args: { image_data: imageData, message: userPrompt },
            callback: function(r) {
                hide_typing();
                $('#km-ai-send').prop('disabled', false);
                if (r.message) {
                    add_bot_message(r.message.reply, r.message.animals || null);
                    if (r.message.actions && r.message.actions.length) render_actions(r.message.actions);
                } else {
                    add_bot_message("I couldn't analyze that image. Make sure vision AI is configured in Settings → AI & Intelligence.");
                }
            },
            error: function() {
                hide_typing();
                $('#km-ai-send').prop('disabled', false);
                add_bot_message("Vision analysis failed. Check your AI provider supports image input.");
            }
        });
    }

    /* ========== DOCUMENT SCANNING / OCR ========== */
    var docScanMode = false;
    var lastScannedData = null;

    function start_document_scan() {
        add_bot_message(
            "📄 **Document Scanner**\n\n"
            + "I can read **handwritten and printed documents** — intake forms, vet records, surrender papers, ID documents, vaccination cards, and more.\n\n"
            + "📷 **Take a photo** of the document with the camera button, or\n"
            + "📁 **Upload** an image of the document using the 📄 button in the toolbar\n\n"
            + "**Tips for best results:**\n"
            + "• Lay the document flat with good lighting\n"
            + "• Capture the full page — don't crop fields\n"
            + "• Avoid shadows and glare\n"
            + "• Handwriting should be as visible as possible\n\n"
            + "After scanning, I'll extract all the info and you can **import it directly** into the system."
        );
        docScanMode = true;
    }

    function handle_doc_upload(e) {
        var file = e.target.files[0];
        if (!file) return;
        if (!file.type.startsWith('image/') && file.type !== 'application/pdf') {
            frappe.show_alert({message: 'Please select an image or PDF file', indicator: 'orange'});
            return;
        }
        if (file.size > 20 * 1024 * 1024) {
            frappe.show_alert({message: 'File must be under 20MB', indicator: 'orange'});
            return;
        }
        var reader = new FileReader();
        reader.onload = function(ev) {
            pendingImageData = ev.target.result;
            docScanMode = true;
            $('#km-camera-feed').hide();
            $('#km-camera-snap').hide();
            $('#km-preview-img').attr('src', pendingImageData).show();
            $('#km-preview-send').show().html('<i class="fa fa-search"></i> Scan & Extract');
            $('#km-vision-preview').show();
        };
        reader.readAsDataURL(file);
        $('#km-doc-file-input').val('');
    }

    /* ========== DOCUMENT SCAN CLARIFICATION STATE ========== */
    var docClarifyState = null;  // {imageData, uncertainties[], currentIdx, extractedData}

    function send_document_scan() {
        if (!pendingImageData) return;
        var imageData = pendingImageData;
        var userHint = $('#km-ai-input').val().trim();
        close_preview();
        docScanMode = false;
        $('#km-preview-send').html('<i class="fa fa-paper-plane"></i> Analyze');

        // Show thumbnail
        var time = frappe.datetime.now_time().substring(0, 5);
        $('#km-ai-messages').append(
            '<div class="km-msg km-msg-user">'
            + '<img src="' + imageData + '" class="km-chat-img-thumb km-doc-thumb" />'
            + '<div class="km-vision-prompt">📄 ' + frappe.utils.escape_html(userHint || 'Power scan — extract all information') + '</div>'
            + '<div class="km-msg-time">' + time + '</div></div>'
        );
        scroll_el('km-ai-messages');
        show_typing('km-ai-messages');
        $('#km-ai-send').prop('disabled', true);

        frappe.call({
            method: 'kennel_management.api.chatbot_document_scan',
            args: {
                image_data: imageData,
                hint: userHint || ''
            },
            callback: function(r) {
                hide_typing();
                $('#km-ai-send').prop('disabled', false);
                if (r.message && r.message.reply) {
                    lastScannedData = r.message.extracted_data || null;
                    add_bot_message(r.message.reply);

                    // Check for uncertainties that need voice clarification
                    var uncertainties = r.message.uncertainties || [];
                    if (uncertainties.length > 0 && lastScannedData) {
                        // Start voice clarification flow
                        docClarifyState = {
                            imageData: imageData,
                            uncertainties: uncertainties,
                            currentIdx: 0,
                            extractedData: lastScannedData
                        };
                        // Show a summary of uncertain fields
                        var uncertMsg = "⚠️ **I found " + uncertainties.length + " field" + (uncertainties.length > 1 ? "s" : "")
                            + " I'm not 100% sure about.** I'll ask you about each one";
                        if (autoSpeak) {
                            uncertMsg += " — speaking the questions now.";
                        } else {
                            uncertMsg += " — click 🎤 or type to answer each question.";
                        }
                        uncertMsg += "\n\n*You can also type \"skip\" to keep my best guess, or \"skip all\" to accept everything as-is.*";
                        add_bot_message(uncertMsg, null, true);

                        // Start asking the first question
                        setTimeout(function() { ask_next_clarification(); }, 800);
                    } else {
                        // No uncertainties — show import actions
                        if (lastScannedData) {
                            render_doc_import_actions(lastScannedData);
                        }
                    }
                } else {
                    add_bot_message("I couldn't read that document. Try taking a clearer photo with better lighting.");
                }
            },
            error: function() {
                hide_typing();
                $('#km-ai-send').prop('disabled', false);
                add_bot_message("Document scanning failed. Check your AI provider configuration.");
            }
        });
    }

    function ask_next_clarification() {
        if (!docClarifyState) return;
        var state = docClarifyState;
        if (state.currentIdx >= state.uncertainties.length) {
            // All clarifications done — clean [uncertain] tags from extracted data and show import
            for (var key in state.extractedData) {
                if (typeof state.extractedData[key] === 'string') {
                    state.extractedData[key] = state.extractedData[key].replace(/\s*\[uncertain\]/gi, '').trim();
                }
            }
            // Remove the _uncertainties key from extracted data
            delete state.extractedData._uncertainties;
            lastScannedData = state.extractedData;
            docClarifyState = null;

            add_bot_message("✅ **All clarifications resolved!** Here's the final extracted data ready for import.");
            render_doc_import_actions(lastScannedData);
            return;
        }

        var item = state.uncertainties[state.currentIdx];
        var questionNum = state.currentIdx + 1;
        var total = state.uncertainties.length;
        var questionMsg = "❓ **Question " + questionNum + " of " + total + "** — *" + (item.field || '').replace(/_/g, ' ') + "*\n\n"
            + item.question;

        // Add the question as a bot message — use voice if in voice mode
        add_bot_message(questionMsg, null, false);

        // If in voice mode, start listening after TTS finishes
        if (autoSpeak) {
            var waitTTS = setInterval(function() {
                if (!isSpeaking) {
                    clearInterval(waitTTS);
                    setTimeout(function() { start_voice_listen(); }, 300);
                }
            }, 200);
        }
    }

    function handle_clarification_answer(answer) {
        if (!docClarifyState) return false;
        var state = docClarifyState;
        var item = state.uncertainties[state.currentIdx];
        var ansLower = answer.toLowerCase().trim();

        // Skip commands
        if (ansLower === 'skip all' || ansLower === 'skip everything' || ansLower === 'accept all') {
            // Accept all remaining as-is
            for (var key in state.extractedData) {
                if (typeof state.extractedData[key] === 'string') {
                    state.extractedData[key] = state.extractedData[key].replace(/\s*\[uncertain\]/gi, '').trim();
                }
            }
            delete state.extractedData._uncertainties;
            lastScannedData = state.extractedData;
            docClarifyState = null;
            add_bot_message("✅ **Got it! Accepting all remaining fields as-is.** Data is ready for import.");
            render_doc_import_actions(lastScannedData);
            return true;
        }

        if (ansLower === 'skip' || ansLower === 'next' || ansLower === 'keep it' || ansLower === 'that\'s fine') {
            // Keep the AI's best guess for this field
            if (item.field && state.extractedData[item.field]) {
                state.extractedData[item.field] = state.extractedData[item.field].toString().replace(/\s*\[uncertain\]/gi, '').trim();
            }
            add_bot_message("👍 Keeping **" + (item.value || 'current value') + "** for " + (item.field || '').replace(/_/g, ' ') + ".");
            state.currentIdx++;
            setTimeout(function() { ask_next_clarification(); }, 500);
            return true;
        }

        // Confirmation answers — user says the value is correct
        if (['yes', 'yeah', 'yep', 'correct', 'that\'s right', 'that is correct', 'right', 'ja'].indexOf(ansLower) > -1) {
            if (item.field && state.extractedData[item.field]) {
                state.extractedData[item.field] = state.extractedData[item.field].toString().replace(/\s*\[uncertain\]/gi, '').trim();
            }
            add_bot_message("✅ Confirmed **" + (item.value || '') + "** for " + (item.field || '').replace(/_/g, ' ') + ".");
            state.currentIdx++;
            setTimeout(function() { ask_next_clarification(); }, 500);
            return true;
        }

        // User provided a correction — send to backend for AI verification, or use directly
        add_user_ai_message(answer);
        show_typing('km-ai-messages');

        frappe.call({
            method: 'kennel_management.api.chatbot_document_clarify',
            args: {
                image_data: state.imageData,
                field: item.field,
                question: item.question,
                user_answer: answer
            },
            callback: function(r) {
                hide_typing();
                if (r.message && r.message.value) {
                    var corrected = r.message.value;
                    state.extractedData[item.field] = corrected;
                    add_bot_message("✅ Updated **" + (item.field || '').replace(/_/g, ' ') + "** to: **" + corrected + "**");
                } else {
                    // Fallback: use user's answer directly
                    state.extractedData[item.field] = answer.trim();
                    add_bot_message("✅ Set **" + (item.field || '').replace(/_/g, ' ') + "** to: **" + answer.trim() + "**");
                }
                state.currentIdx++;
                setTimeout(function() { ask_next_clarification(); }, 500);
            },
            error: function() {
                hide_typing();
                // Use user's answer directly on error
                state.extractedData[item.field] = answer.trim();
                add_bot_message("✅ Set **" + (item.field || '').replace(/_/g, ' ') + "** to: **" + answer.trim() + "**");
                state.currentIdx++;
                setTimeout(function() { ask_next_clarification(); }, 500);
            }
        });

        return true;
    }

    function render_doc_import_actions(data) {
        var actionsHtml = '<div class="km-doc-import-actions">';
        actionsHtml += '<div class="km-doc-import-label">📥 Import this data into:</div>';

        if (data.animal_name || data.breed || data.species) {
            actionsHtml += '<button class="km-doc-import-btn" data-action="admission"><i class="fa fa-paw"></i> Create Animal Admission</button>';
        }
        if (data.client_name || data.phone || data.owner_name) {
            actionsHtml += '<button class="km-doc-import-btn" data-action="client"><i class="fa fa-user"></i> Save as Client Info</button>';
        }
        if (data.vaccination || data.vet_notes || data.medical) {
            actionsHtml += '<button class="km-doc-import-btn" data-action="vet"><i class="fa fa-medkit"></i> Add to Vet Record</button>';
        }
        actionsHtml += '<button class="km-doc-import-btn km-doc-import-copy" data-action="copy"><i class="fa fa-clipboard"></i> Copy All Text</button>';
        actionsHtml += '</div>';

        $('#km-ai-messages').append(actionsHtml);
        scroll_el('km-ai-messages');

        // Bind import actions
        $('#km-ai-messages .km-doc-import-btn').last().parent().find('.km-doc-import-btn').on('click', function() {
            var action = $(this).data('action');
            handle_doc_import(action, data);
        });
    }

    function handle_doc_import(action, data) {
        if (action === 'copy') {
            var text = data._raw_text || JSON.stringify(data, null, 2);
            navigator.clipboard.writeText(text).then(function() {
                frappe.show_alert({message: 'Copied to clipboard!', indicator: 'green'});
            }).catch(function() {
                // Fallback
                var ta = document.createElement('textarea');
                ta.value = text;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                frappe.show_alert({message: 'Copied!', indicator: 'green'});
            });
            return;
        }

        if (action === 'admission') {
            // Map scanned fields to admission data
            var admData = {
                animal_name: data.animal_name || data.name || data.pet_name || 'Unknown (from scan)',
                breed: data.breed || data.dog_breed || '',
                approximate_age: data.age || data.approximate_age || '',
                gender: data.gender || data.sex || 'Unknown',
                color: data.color || data.colour || data.markings || '',
                intake_type: data.intake_type || data.reason || 'Stray',
                health_notes: data.health_notes || data.medical || data.vet_notes || data.conditions || '',
                microchipped: (data.microchip || data.microchipped || '').toString().toLowerCase().startsWith('y') ? 1 : 0
            };
            show_typing('km-ai-messages');
            frappe.call({
                method: 'kennel_management.api.ai_create_admission',
                args: { admission_data: JSON.stringify(admData) },
                callback: function(r) {
                    hide_typing();
                    if (r.message && r.message.success) {
                        add_bot_message(
                            "🎉 **Animal admitted from scanned document!**\n\n"
                            + "• **Animal:** [" + r.message.animal_name + "](/app/animal/" + r.message.animal + ")\n"
                            + "• **Admission:** [" + r.message.admission + "](/app/animal-admission/" + r.message.admission + ")\n"
                            + "• **Kennel:** " + (r.message.kennel || 'Not yet assigned')
                        );
                    } else {
                        add_bot_message("⚠️ " + (r.message && r.message.error || 'Could not create admission from scan.'));
                    }
                },
                error: function() { hide_typing(); add_bot_message("Failed to create admission."); }
            });
            return;
        }

        if (action === 'client') {
            var clientData = {
                purpose: data.purpose || data.reason || 'Document scan',
                full_name: data.client_name || data.owner_name || data.name || data.full_name || 'Unknown',
                phone: data.phone || data.telephone || data.cell || data.contact || '',
                email: data.email || '',
                address: data.address || data.physical_address || data.residential_address || '',
                id_number: data.id_number || data.id || data.identity_number || data.sa_id || ''
            };
            show_typing('km-ai-messages');
            frappe.call({
                method: 'kennel_management.api.ai_save_client_info',
                args: { client_data: JSON.stringify(clientData) },
                callback: function(r) {
                    hide_typing();
                    if (r.message && r.message.success) {
                        add_bot_message(
                            "✅ **Client info saved from scanned document!**\n\n"
                            + "• **Name:** " + r.message.full_name + "\n"
                            + "• **Record:** [View](/app/todo/" + r.message.todo + ")"
                        );
                    } else {
                        add_bot_message("⚠️ " + (r.message && r.message.error || 'Could not save client info.'));
                    }
                },
                error: function() { hide_typing(); add_bot_message("Failed to save client info."); }
            });
            return;
        }

        if (action === 'vet') {
            // Show summary for manual vet entry — there's no direct auto-create yet
            var vetInfo = "🏥 **Extracted Vet Information:**\n\n"
                + (data.vaccination ? "• **Vaccinations:** " + data.vaccination + "\n" : "")
                + (data.vet_notes ? "• **Notes:** " + data.vet_notes + "\n" : "")
                + (data.medical ? "• **Medical:** " + data.medical + "\n" : "")
                + (data.weight ? "• **Weight:** " + data.weight + "\n" : "")
                + (data.temperature ? "• **Temperature:** " + data.temperature + "\n" : "")
                + (data.diagnosis ? "• **Diagnosis:** " + data.diagnosis + "\n" : "")
                + (data.treatment ? "• **Treatment:** " + data.treatment + "\n" : "")
                + (data.medication ? "• **Medication:** " + data.medication + "\n" : "")
                + "\nThis data has been copied to your clipboard. "
                + "Open the [Vet Appointment](/app/vet-appointment/new) form to paste these details.";
            navigator.clipboard.writeText(
                (data.vaccination || '') + '\n' + (data.vet_notes || '') + '\n' + (data.medical || '')
                + '\n' + (data.diagnosis || '') + '\n' + (data.treatment || '') + '\n' + (data.medication || '')
            ).catch(function(){});
            add_bot_message(vetInfo);
        }
    }

    /* ========== ADMISSION ASSISTANT ========== */
    var admissionState = null;

    function start_admission_flow() {
        admissionState = { step: 0, data: {} };
        add_bot_message(
            "🐕 **Animal Admission Assistant**\n\n"
            + "I'll walk you through the full admission form step by step.\n\n"
            + "**Step 1 of 20:** What is the animal's **name**? (or type 'unknown')"
        );
    }

    function start_client_info_flow() {
        admissionState = { step: 'client_0', data: {} };
        add_bot_message(
            "📋 **Client Information Collection**\n\nI'll help gather contact details. "
            + "Is this person:\n\n"
            + "• **Surrendering** an animal (type 'surrender')\n"
            + "• **Adopting** an animal (type 'adopt')\n"
            + "• **Reporting** a lost/found (type 'report')"
        );
    }

    function _admissionPrompt(stepNum, total, label, hint) {
        return "**Step " + stepNum + " of " + total + ":** " + label + (hint ? "\n\n💡 " + hint : "");
    }

    function handle_admission_step(userMsg) {
        var msg = userMsg.trim();
        var s = admissionState;

        // Admission flow (numeric steps)
        if (typeof s.step === 'number') {
            var total = 20;
            switch(s.step) {
                case 0: // Animal Name
                    s.data.animal_name = msg === 'unknown' ? 'Unknown Intake' : msg;
                    s.step = 1;
                    add_bot_message(_admissionPrompt(2, total, "What **species**?",
                        "Type: **Dog** · **Cat** · **Bird** · **Rabbit** · **Reptile** · **Small Animal** · **Farm Animal** · **Other**"));
                    return true;

                case 1: // Species
                    var speciesMap = {dog:'Dog', cat:'Cat', bird:'Bird', rabbit:'Rabbit', reptile:'Reptile', 'small animal':'Small Animal', 'farm animal':'Farm Animal', other:'Other'};
                    s.data.species = speciesMap[msg.toLowerCase()] || msg;
                    s.step = 2;
                    add_bot_message(_admissionPrompt(3, total, "What **breed**?", "e.g. German Shepherd, Siamese, Mixed, Unknown"));
                    return true;

                case 2: // Breed
                    s.data.breed = msg;
                    s.step = 3;
                    add_bot_message(_admissionPrompt(4, total, "**Gender**?", "Type: **Male** · **Female** · **Unknown**"));
                    return true;

                case 3: // Gender
                    var genderMap = {male:'Male', female:'Female', m:'Male', f:'Female', unknown:'Unknown'};
                    s.data.gender = genderMap[msg.toLowerCase()] || msg;
                    s.step = 4;
                    add_bot_message(_admissionPrompt(5, total, "**Estimated age**?", "e.g. '2 years', '6 months', 'puppy', 'senior', 'unknown'"));
                    return true;

                case 4: // Age
                    s.data.estimated_age = msg;
                    s.step = 5;
                    add_bot_message(_admissionPrompt(6, total, "**Color / markings**?", "e.g. 'Black and tan', 'White with spots', or 'unknown'"));
                    return true;

                case 5: // Color
                    s.data.color = msg === 'unknown' ? '' : msg;
                    s.step = 6;
                    add_bot_message(_admissionPrompt(7, total, "**Weight on arrival** (kg)?", "Type a number like '12.5' or 'skip' if unknown"));
                    return true;

                case 6: // Weight
                    if (msg.toLowerCase() !== 'skip') {
                        var w = parseFloat(msg);
                        if (!isNaN(w)) s.data.weight_on_arrival = w;
                    }
                    s.step = 7;
                    add_bot_message(_admissionPrompt(8, total, "**Admission type**?",
                        "Type: **Stray** · **Owner Surrender** · **Rescue** · **Transfer In** · **Confiscation** · **Born in Shelter** · **Return from Adoption** · **Return from Foster**"));
                    return true;

                case 7: // Admission type
                    var typeMap = {
                        'stray':'Stray', 'owner surrender':'Owner Surrender', 'surrender':'Owner Surrender',
                        'rescue':'Rescue', 'transfer':'Transfer In', 'transfer in':'Transfer In',
                        'confiscation':'Confiscation', 'born in shelter':'Born in Shelter', 'born':'Born in Shelter',
                        'return from adoption':'Return from Adoption', 'return adoption':'Return from Adoption',
                        'return from foster':'Return from Foster', 'return foster':'Return from Foster'
                    };
                    s.data.admission_type = typeMap[msg.toLowerCase()] || msg;
                    // Dynamic next step based on type
                    if (s.data.admission_type === 'Owner Surrender') {
                        s.step = 8;
                        add_bot_message(_admissionPrompt(9, total, "**Surrenderer's full name**?", "The person surrendering the animal"));
                    } else if (['Stray', 'Rescue', 'Confiscation'].includes(s.data.admission_type)) {
                        s.step = 11;
                        add_bot_message(_admissionPrompt(9, total, "**Where was the animal found**?", "Address or area description"));
                    } else {
                        s.step = 12;
                        add_bot_message(_admissionPrompt(9, total, "**Overall condition on arrival**?",
                            "Type: **Excellent** · **Good** · **Fair** · **Poor** · **Critical**"));
                    }
                    return true;

                case 8: // Surrenderer name
                    s.data.surrendered_by_name = msg;
                    s.step = 9;
                    add_bot_message(_admissionPrompt(10, total, "**Surrenderer's phone number**?", "Or type 'none'"));
                    return true;

                case 9: // Surrenderer phone
                    s.data.surrendered_by_phone = msg === 'none' ? '' : msg;
                    s.step = 10;
                    add_bot_message(_admissionPrompt(11, total, "**Reason for surrender**?",
                        "Type: **Moving** · **Landlord Issues** · **Allergies** · **Financial** · **Behavior Problems** · **Too Many Animals** · **Health Issues** · **No Time** · **Other**"));
                    return true;

                case 10: // Surrender reason
                    s.data.surrender_reason = msg;
                    s.step = 12;
                    add_bot_message(_admissionPrompt(12, total, "**Overall condition on arrival**?",
                        "Type: **Excellent** · **Good** · **Fair** · **Poor** · **Critical**"));
                    return true;

                case 11: // Found location
                    s.data.found_location = msg;
                    s.step = 12;
                    add_bot_message(_admissionPrompt(10, total, "**Overall condition on arrival**?",
                        "Type: **Excellent** · **Good** · **Fair** · **Poor** · **Critical**"));
                    return true;

                case 12: // Condition
                    var condMap = {excellent:'Excellent', good:'Good', fair:'Fair', poor:'Poor', critical:'Critical'};
                    s.data.condition_on_arrival = condMap[msg.toLowerCase()] || msg;
                    s.step = 13;
                    add_bot_message(_admissionPrompt(13, total, "**Initial temperament**?",
                        "Type: **Friendly** · **Shy** · **Aggressive** · **Fearful** · **Calm** · **Anxious**"));
                    return true;

                case 13: // Temperament
                    var tempMap = {friendly:'Friendly', shy:'Shy', aggressive:'Aggressive', fearful:'Fearful', calm:'Calm', anxious:'Anxious'};
                    s.data.initial_temperament = tempMap[msg.toLowerCase()] || msg;
                    s.step = 14;
                    add_bot_message(_admissionPrompt(14, total, "**Vaccination status**?",
                        "Type: **Yes** · **No** · **Unknown** · **Partial**"));
                    return true;

                case 14: // Vaccination
                    var vacMap = {yes:'Yes', no:'No', unknown:'Unknown', partial:'Partial'};
                    s.data.is_vaccinated = vacMap[msg.toLowerCase()] || msg;
                    s.step = 15;
                    add_bot_message(_admissionPrompt(15, total, "**Spayed / Neutered**?",
                        "Type: **Yes** · **No** · **Unknown**"));
                    return true;

                case 15: // Spay/neuter
                    var fixMap = {yes:'Yes', no:'No', unknown:'Unknown'};
                    s.data.is_spayed_neutered = fixMap[msg.toLowerCase()] || msg;
                    s.step = 16;
                    add_bot_message(_admissionPrompt(16, total, "**Microchipped**?",
                        "Type: **Yes** · **No** · **Unknown**"));
                    return true;

                case 16: // Microchipped
                    var chipMap = {yes:'Yes', no:'No', unknown:'Unknown'};
                    s.data.is_microchipped = chipMap[msg.toLowerCase()] || msg;
                    s.step = 17;
                    add_bot_message(_admissionPrompt(17, total, "Any **injuries or health concerns**?",
                        "Describe visible injuries/conditions, or type 'none'"));
                    return true;

                case 17: // Injuries
                    s.data.injuries_description = msg.toLowerCase() === 'none' ? '' : msg;
                    s.step = 18;
                    add_bot_message(_admissionPrompt(18, total, "Does this animal **require quarantine**?",
                        "Type: **Yes** or **No**"));
                    return true;

                case 18: // Quarantine
                    s.data.requires_quarantine = (msg.toLowerCase() === 'yes' || msg.toLowerCase() === 'y') ? 1 : 0;
                    s.step = 19;
                    add_bot_message(_admissionPrompt(19, total, "Any **additional intake notes**?",
                        "Medical history, behavioral observations, items surrendered with animal, etc. Type 'none' to skip."));
                    return true;

                case 19: // Notes
                    s.data.intake_notes = msg.toLowerCase() === 'none' ? '' : msg;
                    s.step = 20;
                    // Build summary
                    var sum = "✅ **Admission Summary — Please Review:**\n\n"
                        + "• **Name:** " + s.data.animal_name + "\n"
                        + "• **Species:** " + (s.data.species || 'Dog') + "\n"
                        + "• **Breed:** " + (s.data.breed || 'Unknown') + "\n"
                        + "• **Gender:** " + (s.data.gender || 'Unknown') + "\n"
                        + "• **Age:** " + (s.data.estimated_age || 'Unknown') + "\n"
                        + "• **Color:** " + (s.data.color || 'Not specified') + "\n"
                        + "• **Weight:** " + (s.data.weight_on_arrival ? s.data.weight_on_arrival + " kg" : 'Not recorded') + "\n"
                        + "• **Admission Type:** " + (s.data.admission_type || 'Stray') + "\n";
                    if (s.data.surrendered_by_name) {
                        sum += "• **Surrendered By:** " + s.data.surrendered_by_name
                            + (s.data.surrendered_by_phone ? " (" + s.data.surrendered_by_phone + ")" : "") + "\n"
                            + "• **Surrender Reason:** " + (s.data.surrender_reason || 'Not given') + "\n";
                    }
                    if (s.data.found_location) {
                        sum += "• **Found Location:** " + s.data.found_location + "\n";
                    }
                    sum += "• **Condition:** " + (s.data.condition_on_arrival || 'Fair') + "\n"
                        + "• **Temperament:** " + (s.data.initial_temperament || 'Unknown') + "\n"
                        + "• **Vaccinated:** " + (s.data.is_vaccinated || 'Unknown') + "\n"
                        + "• **Spayed/Neutered:** " + (s.data.is_spayed_neutered || 'Unknown') + "\n"
                        + "• **Microchipped:** " + (s.data.is_microchipped || 'Unknown') + "\n"
                        + "• **Injuries:** " + (s.data.injuries_description || 'None noted') + "\n"
                        + "• **Quarantine:** " + (s.data.requires_quarantine ? 'Yes' : 'No') + "\n"
                        + (s.data.intake_notes ? "• **Notes:** " + s.data.intake_notes + "\n" : "")
                        + "\n**Step 20/20:** Type **confirm** to create the admission, or **cancel** to discard.";
                    add_bot_message(sum);
                    return true;

                case 20: // Confirm
                    if (msg.toLowerCase() === 'confirm') {
                        submit_admission(s.data);
                    } else {
                        add_bot_message("Admission cancelled. No worries — you can start again anytime. 🐾");
                        admissionState = null;
                    }
                    return true;
            }
        }

        // Client info flow
        if (typeof s.step === 'string' && s.step.startsWith('client_')) {
            var cStep = parseInt(s.step.split('_')[1]);
            switch(cStep) {
                case 0: // Type
                    s.data.purpose = msg.toLowerCase();
                    s.step = 'client_1';
                    add_bot_message("**Client's full name?**");
                    return true;
                case 1: // Name
                    s.data.full_name = msg;
                    s.step = 'client_2';
                    add_bot_message("**Phone number?**");
                    return true;
                case 2: // Phone
                    s.data.phone = msg;
                    s.step = 'client_3';
                    add_bot_message("**Email address?** (or 'none')");
                    return true;
                case 3: // Email
                    s.data.email = msg === 'none' ? '' : msg;
                    s.step = 'client_4';
                    add_bot_message("**Physical address?**");
                    return true;
                case 4: // Address
                    s.data.address = msg;
                    s.step = 'client_5';
                    add_bot_message("**ID number?** (or 'none')");
                    return true;
                case 5: // ID
                    s.data.id_number = msg === 'none' ? '' : msg;
                    s.step = 'client_6';
                    var csummary = "✅ **Client Details Collected:**\n\n"
                        + "• **Purpose:** " + s.data.purpose + "\n"
                        + "• **Name:** " + s.data.full_name + "\n"
                        + "• **Phone:** " + s.data.phone + "\n"
                        + "• **Email:** " + (s.data.email || 'Not provided') + "\n"
                        + "• **Address:** " + s.data.address + "\n"
                        + "• **ID:** " + (s.data.id_number || 'Not provided') + "\n\n"
                        + "Type **save** to store this, or **cancel** to discard.";
                    add_bot_message(csummary);
                    return true;
                case 6: // Confirm
                    if (msg.toLowerCase() === 'save') {
                        save_client_info(s.data);
                    } else {
                        add_bot_message("Client info discarded. 📋");
                        admissionState = null;
                    }
                    return true;
            }
        }
        return false;
    }

    function submit_admission(data) {
        show_typing('km-ai-messages');
        frappe.call({
            method: 'kennel_management.api.ai_create_admission',
            args: { admission_data: JSON.stringify(data) },
            callback: function(r) {
                hide_typing();
                admissionState = null;
                if (r.message && r.message.success) {
                    add_bot_message(
                        "🎉 **Admission created successfully!**\n\n"
                        + "• **Animal:** [" + r.message.animal_name + "](/app/animal/" + r.message.animal + ")\n"
                        + "• **Admission:** [" + r.message.admission + "](/app/animal-admission/" + r.message.admission + ")\n"
                        + "• **Kennel:** " + (r.message.kennel || 'Not yet assigned') + "\n\n"
                        + "The dog is now in the system. You can assign a kennel and schedule a vet check."
                    );
                } else {
                    add_bot_message("⚠️ Could not create admission: " + (r.message && r.message.error || 'Unknown error') + "\n\nYou can try again or create it manually via the Admission form.");
                }
            },
            error: function() {
                hide_typing();
                admissionState = null;
                add_bot_message("Failed to create admission. Please try manually.");
            }
        });
    }

    function save_client_info(data) {
        show_typing('km-ai-messages');
        frappe.call({
            method: 'kennel_management.api.ai_save_client_info',
            args: { client_data: JSON.stringify(data) },
            callback: function(r) {
                hide_typing();
                admissionState = null;
                if (r.message && r.message.success) {
                    add_bot_message(
                        "✅ **Client info saved!**\n\n"
                        + "• **Name:** " + r.message.full_name + "\n"
                        + "• **Record:** [View](/app/todo/" + r.message.todo + ")\n\n"
                        + "The info has been logged as a task for follow-up."
                    );
                } else {
                    add_bot_message("⚠️ Could not save: " + (r.message && r.message.error || 'Unknown error'));
                }
            },
            error: function() {
                hide_typing();
                admissionState = null;
                add_bot_message("Failed to save client information.");
            }
        });
    }

    /* ========== TEXT-TO-SPEECH ========== */
    var ttsAudio = null;

    function speak_text(text, voiceModeOnly) {
        // Stop any currently playing audio
        stop_speaking();
        isSpeaking = true;

        // Start browser TTS immediately for instant feedback
        browser_speak(text);

        // In voice conversation mode, skip OpenAI TTS for zero-latency response
        if (voiceModeOnly) return;

        // Try to upgrade to AI TTS (higher quality) in parallel
        frappe.call({
            method: 'kennel_management.api.text_to_speech',
            args: { text: text },
            callback: function(r) {
                if (r.message && r.message.audio) {
                    // Got AI TTS — stop browser TTS and play high-quality audio
                    if (speechSynth) speechSynth.cancel();
                    ttsAudio = new Audio('data:audio/mp3;base64,' + r.message.audio);
                    ttsAudio.onended = function() { isSpeaking = false; };
                    ttsAudio.play().catch(function(e) {
                        console.warn('TTS audio play failed:', e);
                        // Browser TTS already started as fallback, just mark done
                        isSpeaking = false;
                    });
                }
                // If no AI audio, browser TTS is already playing — no action needed
            },
            error: function() {
                // Browser TTS already running as fallback — no action needed
            }
        });
    }

    function stop_speaking() {
        if (ttsAudio) { ttsAudio.pause(); ttsAudio.currentTime = 0; ttsAudio = null; }
        if (speechSynth) speechSynth.cancel();
        isSpeaking = false;
    }

    function browser_speak(text) {
        if (!speechSynth) {
            frappe.show_alert({message: 'Text-to-speech not supported', indicator: 'orange'});
            return;
        }
        speechSynth.cancel();
        var cleaned = text.replace(/\*\*(.*?)\*\*/g, '$1').replace(/[•\n]/g, '. ').replace(/\s+/g, ' ').trim();
        var utter = new SpeechSynthesisUtterance(cleaned);
        utter.rate = 1.0;
        utter.pitch = 1.0;
        utter.onend = function() { isSpeaking = false; };
        utter.onerror = function() { isSpeaking = false; };
        var voices = speechSynth.getVoices();
        var pref = voices.find(function(v) { return v.lang.startsWith('en') && v.name.indexOf('Female') > -1; })
            || voices.find(function(v) { return v.lang.startsWith('en-US'); })
            || voices.find(function(v) { return v.lang.startsWith('en'); });
        if (pref) utter.voice = pref;
        speechSynth.speak(utter);
    }

    /* ========== SPEECH-TO-TEXT ========== */
    var mediaRecorder = null;
    var audioChunks = [];

    function toggle_stt() {
        // If already recording, stop and send
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            return;
        }
        if (isListening) { stop_stt(); return; }

        // Use voice listen with silence detection (ChatGPT-like: auto-stops when you stop talking)
        start_voice_listen();
    }

    function start_browser_stt() {
        var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) { frappe.show_alert({message: 'Speech recognition not supported', indicator: 'orange'}); return; }

        recognition = new SR();
        recognition.lang = 'en-US';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;
        recognition.onstart = function() { isListening = true; $('#km-mic-btn').addClass('km-mic-active'); };
        recognition.onresult = function(e) {
            var t = e.results[0][0].transcript;
            $('#km-ai-input').val(t);
            stop_stt();
            if (t.trim()) { lastMsgWasVoice = true; send_ai_message(t.trim()); }
        };
        recognition.onerror = function() { stop_stt(); };
        recognition.onend = function() { stop_stt(); };
        recognition.start();
    }

    function stop_stt() {
        isListening = false;
        $('#km-mic-btn').removeClass('km-mic-active');
        if (recognition) { try { recognition.stop(); } catch(e) {} recognition = null; }
        // Also clean up voice listen state if active
        if (voiceAudioCtx || voiceStream) cleanup_voice_listen(true);
        // Resume wake word listener
        resume_wake_listener();
    }

    /* ========== VOICE CONVERSATION LISTEN (Whisper + auto silence detection) ========== */
    var voiceAudioCtx = null;
    var voiceSilenceTimer = null;
    var voiceAnalyser = null;
    var voiceStream = null;
    var SILENCE_THRESHOLD = 15;       // RMS below this = silence (0-128 scale)
    var SILENCE_DURATION = 1500;      // ms of silence before auto-stop
    var SPEECH_MIN_DURATION = 600;    // ms — must record at least this long before silence-stop
    var MAX_LISTEN_DURATION = 15000;  // ms — max recording length

    function start_voice_listen() {
        // Uses Whisper API for accurate transcription + AudioContext for auto silence detection
        if (isListening) return;

        pause_wake_listener();

        navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
            voiceStream = stream;
            audioChunks = [];

            // Set up silence detection via AudioContext analyser
            voiceAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
            var source = voiceAudioCtx.createMediaStreamSource(stream);
            voiceAnalyser = voiceAudioCtx.createAnalyser();
            voiceAnalyser.fftSize = 512;
            source.connect(voiceAnalyser);

            // Start MediaRecorder for Whisper
            var mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
            mediaRecorder = mimeType
                ? new MediaRecorder(stream, { mimeType: mimeType })
                : new MediaRecorder(stream);

            mediaRecorder.ondataavailable = function(e) {
                if (e.data.size > 0) audioChunks.push(e.data);
            };

            mediaRecorder.onstop = function() {
                cleanup_voice_listen(false);
                var blob = new Blob(audioChunks, { type: 'audio/webm' });
                audioChunks = [];
                mediaRecorder = null;

                // Skip if too small (< 1KB = no real speech)
                if (blob.size < 1000) {
                    resume_wake_listener();
                    return;
                }

                var reader = new FileReader();
                reader.onload = function(ev) {
                    show_typing('km-ai-messages');
                    frappe.call({
                        method: 'kennel_management.api.speech_to_text',
                        args: { audio_data: ev.target.result },
                        callback: function(r) {
                            hide_typing();
                            resume_wake_listener();
                            if (r.message && r.message.text) {
                                var t = r.message.text.trim();
                                if (t) {
                                    lastMsgWasVoice = true;
                                    $('#km-ai-input').val(t);
                                    send_ai_message(t);
                                }
                            }
                        },
                        error: function() {
                            hide_typing();
                            resume_wake_listener();
                        }
                    });
                };
                reader.readAsDataURL(blob);
            };

            mediaRecorder.start(250); // collect data every 250ms
            isListening = true;
            $('#km-mic-btn').addClass('km-mic-active');
            frappe.show_alert({message: 'Listening... speak now 🎤', indicator: 'blue'});

            // Start silence detection loop
            var recordingStart = Date.now();
            var lastSpeechTime = Date.now();
            var speechDetected = false;
            var dataBuffer = new Uint8Array(voiceAnalyser.frequencyBinCount);

            function checkSilence() {
                if (!isListening || !voiceAnalyser) return;

                voiceAnalyser.getByteTimeDomainData(dataBuffer);
                // Calculate RMS volume
                var sum = 0;
                for (var i = 0; i < dataBuffer.length; i++) {
                    var val = dataBuffer[i] - 128;
                    sum += val * val;
                }
                var rms = Math.sqrt(sum / dataBuffer.length);

                var elapsed = Date.now() - recordingStart;

                if (rms > SILENCE_THRESHOLD) {
                    lastSpeechTime = Date.now();
                    speechDetected = true;
                }

                var silentFor = Date.now() - lastSpeechTime;

                // Auto-stop conditions:
                // 1. Speech was detected and silence has lasted long enough
                // 2. Max recording duration reached
                if ((speechDetected && elapsed > SPEECH_MIN_DURATION && silentFor > SILENCE_DURATION)
                    || elapsed > MAX_LISTEN_DURATION) {
                    if (mediaRecorder && mediaRecorder.state === 'recording') {
                        mediaRecorder.stop();
                    }
                    return;
                }

                // If no speech after 8 seconds, stop listening (user didn't speak)
                if (!speechDetected && elapsed > 8000) {
                    cleanup_voice_listen(true);
                    resume_wake_listener();
                    return;
                }

                voiceSilenceTimer = requestAnimationFrame(checkSilence);
            }

            voiceSilenceTimer = requestAnimationFrame(checkSilence);

        }).catch(function(err) {
            console.warn('Voice listen mic error:', err);
            isListening = false;
            resume_wake_listener();
        });
    }

    function cleanup_voice_listen(stopRecorder) {
        if (voiceSilenceTimer) { cancelAnimationFrame(voiceSilenceTimer); voiceSilenceTimer = null; }
        if (voiceAudioCtx) { try { voiceAudioCtx.close(); } catch(e) {} voiceAudioCtx = null; }
        voiceAnalyser = null;
        if (voiceStream) { voiceStream.getTracks().forEach(function(t) { t.stop(); }); voiceStream = null; }
        if (stopRecorder && mediaRecorder && mediaRecorder.state === 'recording') {
            try { mediaRecorder.stop(); } catch(e) {}
        }
        isListening = false;
        $('#km-mic-btn').removeClass('km-mic-active');
    }

    /* ========== VOICE/VIDEO CALLING (WebRTC) ========== */
    var rtcConfig = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

    function setup_call_listeners() {
        frappe.realtime.on('km_incoming_call', function(data) {
            if (callState) return;
            show_incoming_call(data);
        });
        frappe.realtime.on('km_call_signal', function(data) {
            if (!callState || callState.callId !== data.call_id) return;
            handle_signal(data);
        });
    }

    function show_incoming_call(data) {
        callState = {
            callId: data.call_id, type: data.call_type,
            peer: data.from_user, peerName: data.from_name,
            pc: null, localStream: null, remoteStream: null,
            direction: 'incoming', timerSeconds: 0, timerInterval: null, muted: false
        };
        $('#km-call-status').text('Incoming ' + data.call_type + ' call...');
        $('#km-call-peer-name').text(data.from_name);
        $('#km-call-type-icon').html('<i class="fa ' + (data.call_type === 'video' ? 'fa-video-camera' : 'fa-phone') + '"></i>');
        $('#km-call-accept, #km-call-reject').show();
        $('#km-call-end, #km-call-mute').hide();
        $('#km-call-timer, #km-call-video-container').hide();
        $('#km-call-overlay').addClass('active km-incoming');
        start_ringtone();
    }

    function start_ringtone() {
        stop_ringtone();
        try {
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            ringtoneInterval = setInterval(function() {
                var osc = ctx.createOscillator();
                var gain = ctx.createGain();
                osc.connect(gain); gain.connect(ctx.destination);
                osc.frequency.value = 440; gain.gain.value = 0.1;
                osc.start(); osc.stop(ctx.currentTime + 0.2);
            }, 1000);
        } catch(e) {}
    }

    function stop_ringtone() {
        if (ringtoneInterval) { clearInterval(ringtoneInterval); ringtoneInterval = null; }
    }

    function start_call(toUser, toName, callType) {
        if (callState) { frappe.show_alert({message: 'Already in a call', indicator: 'orange'}); return; }
        callState = {
            callId: null, type: callType,
            peer: toUser, peerName: toName,
            pc: null, localStream: null, remoteStream: null,
            direction: 'outgoing', timerSeconds: 0, timerInterval: null, muted: false
        };
        $('#km-call-status').text('Calling...');
        $('#km-call-peer-name').text(toName);
        $('#km-call-type-icon').html('<i class="fa ' + (callType === 'video' ? 'fa-video-camera' : 'fa-phone') + '"></i>');
        $('#km-call-accept, #km-call-reject').hide();
        $('#km-call-end, #km-call-mute').show();
        $('#km-call-timer, #km-call-video-container').hide();
        $('#km-call-overlay').addClass('active').removeClass('km-incoming');

        frappe.call({
            method: 'kennel_management.api.initiate_call',
            args: { to_user: toUser, call_type: callType },
            callback: function(r) {
                if (r.message) { callState.callId = r.message.call_id; setup_peer_connection(true); }
            },
            error: function() {
                frappe.show_alert({message: 'Failed to initiate call', indicator: 'red'});
                cleanup_call();
            }
        });
    }

    function accept_call() {
        if (!callState || callState.direction !== 'incoming') return;
        stop_ringtone();
        $('#km-call-overlay').removeClass('km-incoming');
        $('#km-call-accept, #km-call-reject').hide();
        $('#km-call-end, #km-call-mute').show();
        $('#km-call-status').text('Connecting...');
        send_signal('call-accept', {});
        setup_peer_connection(false);
    }

    function reject_call() {
        if (!callState) return;
        stop_ringtone();
        send_signal('call-reject', {});
        cleanup_call();
    }

    function end_call() {
        if (!callState) return;
        send_signal('call-end', {});
        cleanup_call();
    }

    function toggle_mute() {
        if (!callState || !callState.localStream) return;
        callState.muted = !callState.muted;
        callState.localStream.getAudioTracks().forEach(function(t) { t.enabled = !callState.muted; });
        $('#km-call-mute').toggleClass('muted', callState.muted);
        $('#km-call-mute i').toggleClass('fa-microphone fa-microphone-slash');
    }

    function setup_peer_connection(isInitiator) {
        var constraints = callState.type === 'video'
            ? { audio: true, video: { width: 320, height: 240 } }
            : { audio: true };

        navigator.mediaDevices.getUserMedia(constraints).then(function(stream) {
            callState.localStream = stream;
            callState.pc = new RTCPeerConnection(rtcConfig);
            stream.getTracks().forEach(function(track) { callState.pc.addTrack(track, stream); });

            if (callState.type === 'video') {
                var lv = document.getElementById('km-local-video');
                if (lv) lv.srcObject = stream;
                $('#km-call-video-container').show();
            }

            callState.pc.onicecandidate = function(e) {
                if (e.candidate) send_signal('ice-candidate', { candidate: e.candidate });
            };

            callState.pc.ontrack = function(e) {
                callState.remoteStream = e.streams[0];
                if (callState.type === 'video') {
                    var rv = document.getElementById('km-remote-video');
                    if (rv) rv.srcObject = e.streams[0];
                } else {
                    var ra = document.getElementById('km-remote-audio');
                    if (ra) ra.srcObject = e.streams[0];
                }
                $('#km-call-status').text('Connected');
                start_call_timer();
            };

            callState.pc.onconnectionstatechange = function() {
                if (callState && callState.pc) {
                    var s = callState.pc.connectionState;
                    if (s === 'disconnected' || s === 'failed' || s === 'closed') cleanup_call();
                }
            };

            if (isInitiator) {
                callState.pc.createOffer().then(function(offer) {
                    return callState.pc.setLocalDescription(offer);
                }).then(function() {
                    send_signal('offer', { sdp: callState.pc.localDescription });
                });
            }
        }).catch(function(err) {
            frappe.show_alert({message: 'Could not access microphone/camera: ' + err.message, indicator: 'red'});
            if (callState) send_signal('call-end', {});
            cleanup_call();
        });
    }

    function handle_signal(data) {
        var sig = data.signal_type;
        var payload = data.payload || {};

        if (sig === 'call-accept') {
            $('#km-call-status').text('Connecting...');
        } else if (sig === 'call-reject') {
            frappe.show_alert({message: data.from_name + ' declined the call', indicator: 'orange'});
            cleanup_call();
        } else if (sig === 'call-end') {
            frappe.show_alert({message: 'Call ended', indicator: 'blue'});
            cleanup_call();
        } else if (sig === 'offer' && callState && callState.pc) {
            callState.pc.setRemoteDescription(new RTCSessionDescription(payload.sdp)).then(function() {
                return callState.pc.createAnswer();
            }).then(function(answer) {
                return callState.pc.setLocalDescription(answer);
            }).then(function() {
                send_signal('answer', { sdp: callState.pc.localDescription });
            });
        } else if (sig === 'answer' && callState && callState.pc) {
            callState.pc.setRemoteDescription(new RTCSessionDescription(payload.sdp));
        } else if (sig === 'ice-candidate' && callState && callState.pc && payload.candidate) {
            callState.pc.addIceCandidate(new RTCIceCandidate(payload.candidate));
        }
    }

    function send_signal(signalType, payload) {
        if (!callState) return;
        frappe.call({
            method: 'kennel_management.api.call_signal',
            args: {
                to_user: callState.peer,
                call_id: callState.callId,
                signal_type: signalType,
                payload: JSON.stringify(payload)
            },
            async: true
        });
    }

    function start_call_timer() {
        if (!callState) return;
        callState.timerSeconds = 0;
        $('#km-call-timer').show().text('00:00');
        callState.timerInterval = setInterval(function() {
            if (!callState) return;
            callState.timerSeconds++;
            var m = Math.floor(callState.timerSeconds / 60);
            var s = callState.timerSeconds % 60;
            $('#km-call-timer').text((m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s);
        }, 1000);
    }

    function cleanup_call() {
        stop_ringtone();
        if (callState) {
            if (callState.timerInterval) clearInterval(callState.timerInterval);
            if (callState.localStream) callState.localStream.getTracks().forEach(function(t) { t.stop(); });
            if (callState.pc) try { callState.pc.close(); } catch(e) {}
        }
        callState = null;
        var rv = document.getElementById('km-remote-video');
        var lv = document.getElementById('km-local-video');
        var ra = document.getElementById('km-remote-audio');
        if (rv) rv.srcObject = null;
        if (lv) lv.srcObject = null;
        if (ra) ra.srcObject = null;
        $('#km-call-overlay').removeClass('active km-incoming');
    }

    /* ========== INTERNAL MESSAGING ========== */
    function load_user_list() {
        frappe.call({
            method: 'kennel_management.api.get_chat_users',
            callback: function(r) {
                var users = r.message || [];
                var container = $('#km-user-list');
                if (!users.length) {
                    container.html('<div class="km-empty-state"><i class="fa fa-users"></i><p>No team members found</p></div>');
                    return;
                }
                var html = '';
                users.forEach(function(u) {
                    var initial = (u.full_name || 'U').charAt(0).toUpperCase();
                    var preview = u.last_message ? frappe.utils.escape_html(u.last_message).substring(0, 35) : 'Start a conversation';
                    var time = u.last_time ? frappe.datetime.prettyDate(u.last_time) : '';
                    var unread = u.unread || 0;
                    html += '<div class="km-user-item" data-user="' + u.email + '" data-fullname="' + frappe.utils.escape_html(u.full_name) + '">'
                        + '<div class="km-user-avatar">' + initial + '</div>'
                        + '<div class="km-user-info">'
                        + '<div class="km-user-name">' + frappe.utils.escape_html(u.full_name) + '</div>'
                        + '<div class="km-user-preview">' + preview + '</div>'
                        + '</div>'
                        + '<div class="km-user-meta">'
                        + '<div class="km-user-time">' + time + '</div>'
                        + (unread ? '<div class="km-user-unread">' + unread + '</div>' : '')
                        + '</div></div>';
                });
                container.html(html);
                container.find('.km-user-item').on('click', function() {
                    open_dm($(this).data('user'), $(this).data('fullname'));
                });
            }
        });
    }

    function open_dm(user, fullName) {
        dmUser = user;
        dmUserName = fullName;
        var initial = (fullName || 'U').charAt(0).toUpperCase();
        $('#km-msg-list-view').hide();
        $('#km-dm-view').css('display', 'flex');
        $('.km-dm-name').text(fullName);
        $('.km-dm-avatar').text(initial);
        $('#km-dm-messages').html('<div class="km-empty-state"><i class="fa fa-spinner fa-spin"></i><p>Loading...</p></div>');
        load_dm_messages();
        if (dmPollTimer) clearInterval(dmPollTimer);
        dmPollTimer = setInterval(load_dm_messages, 5000);
    }

    function close_dm() {
        dmUser = null;
        dmUserName = '';
        if (dmPollTimer) clearInterval(dmPollTimer);
        $('#km-dm-view').hide();
        $('#km-msg-list-view').show();
        load_user_list();
    }

    function load_dm_messages() {
        if (!dmUser) return;
        frappe.call({
            method: 'kennel_management.api.get_dm_messages',
            args: { other_user: dmUser },
            callback: function(r) {
                var msgs = r.message || [];
                var container = $('#km-dm-messages');
                if (!msgs.length) {
                    container.html('<div class="km-empty-state"><i class="fa fa-comment-o"></i><p>No messages yet.<br>Say hello!</p></div>');
                    return;
                }
                var html = '';
                var lastDate = '';
                msgs.forEach(function(m) {
                    var date = m.creation.substring(0, 10);
                    if (date !== lastDate) {
                        lastDate = date;
                        var label = (date === frappe.datetime.get_today()) ? 'Today' : frappe.datetime.str_to_user(date);
                        html += '<div class="km-date-sep">' + label + '</div>';
                    }
                    var isMe = m.sender === frappe.session.user;
                    var cls = isMe ? 'km-msg-me' : 'km-msg-other';
                    var time = m.creation.substring(11, 16);
                    html += '<div class="km-msg ' + cls + '">';
                    if (!isMe) html += '<div class="km-msg-sender">' + frappe.utils.escape_html(m.sender_name || m.sender) + '</div>';
                    html += frappe.utils.escape_html(m.content);
                    html += '<div class="km-msg-time">' + time + '</div></div>';
                });
                container.html(html);
                scroll_el('km-dm-messages');
            }
        });
    }

    function send_dm(text) {
        var time = frappe.datetime.now_time().substring(0, 5);
        $('#km-dm-messages .km-empty-state').remove();
        $('#km-dm-messages').append(
            '<div class="km-msg km-msg-me">' + frappe.utils.escape_html(text) + '<div class="km-msg-time">' + time + '</div></div>'
        );
        scroll_el('km-dm-messages');
        $('#km-dm-input').val('');
        frappe.call({
            method: 'kennel_management.api.send_dm_message',
            args: { to_user: dmUser, content: text },
            error: function() { frappe.show_alert({message: 'Failed to send message', indicator: 'red'}); }
        });
    }

    function check_unread() {
        frappe.call({
            method: 'kennel_management.api.get_unread_count',
            callback: function(r) {
                unreadCount = (r.message || 0);
                var badge = $('.km-fab-badge');
                var tabBadge = $('#km-msg-badge');
                if (unreadCount > 0) {
                    badge.text(unreadCount).addClass('show');
                    tabBadge.text(unreadCount).addClass('show');
                } else {
                    badge.removeClass('show');
                    tabBadge.removeClass('show');
                }
            }
        });
    }

    /* ========== HELPERS ========== */
    /* ========== CHAT HISTORY PERSISTENCE ========== */
    function save_chat_message(role, text, animals, time) {
        try {
            var history = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
            history.push({
                role: role,
                text: text,
                animals: animals || null,
                time: time,
                ts: Date.now()
            });
            // Keep only the most recent messages
            if (history.length > CHAT_MAX_MESSAGES) {
                history = history.slice(history.length - CHAT_MAX_MESSAGES);
            }
            localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(history));
        } catch(e) {
            // localStorage might be full or unavailable
            console.warn('Chat history save failed:', e);
        }
    }

    function restore_chat_history() {
        try {
            var history = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
            if (!history.length) return;

            // Expire messages older than 24 hours
            var cutoff = Date.now() - (24 * 60 * 60 * 1000);
            history = history.filter(function(m) { return m.ts > cutoff; });

            if (!history.length) {
                localStorage.removeItem(CHAT_STORAGE_KEY);
                return;
            }

            // Save cleaned history back
            localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(history));

            // Hide welcome orb and suggestion cards since we have history
            $('.km-scout-orb').hide();
            $('.km-suggestion-cards').hide();

            // Re-render each message
            history.forEach(function(m) {
                if (m.role === 'user') {
                    add_user_ai_message(m.text, true);
                } else {
                    add_bot_message(m.text, m.animals, true, true);
                }
            });

            // Show a separator so user knows where old messages end
            $('#km-ai-messages').append(
                '<div class="km-history-sep"><span>Previous conversation restored</span></div>'
            );
            scroll_el('km-ai-messages');
        } catch(e) {
            console.warn('Chat history restore failed:', e);
        }
    }

    function clear_chat_history() {
        try { localStorage.removeItem(CHAT_STORAGE_KEY); } catch(e) {}
        // Remove all messages but keep the welcome orb and suggestion cards
        $('#km-ai-messages').children().not('.km-scout-orb, .km-suggestion-cards').remove();
        $('.km-scout-orb').show();
        $('.km-suggestion-cards').show();
        frappe.show_alert({message: 'Chat history cleared', indicator: 'green'});
    }

    function show_typing(id) {
        $('#' + id).append('<div class="km-typing" id="km-typing"><span class="km-typing-label">Scout is thinking</span><div class="km-typing-dot"></div><div class="km-typing-dot"></div><div class="km-typing-dot"></div></div>');
        scroll_el(id);
    }
    function hide_typing() { $('#km-typing').remove(); }

    function scroll_el(id) {
        var el = document.getElementById(id);
        if (el) el.scrollTop = el.scrollHeight;
    }

    function format_bot_text(text) {
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\n/g, '<br>');
        return text;
    }

    function render_actions(actions) {
        var html = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px;">';
        actions.forEach(function(a) {
            html += '<a href="' + a.route + '" style="font-size:12px;color:#6366f1;font-weight:500;text-decoration:underline;">'
                + frappe.utils.escape_html(a.label) + '</a>';
        });
        html += '</div>';
        $('#km-ai-messages').children().last().append(html);
        scroll_el('km-ai-messages');
    }

    /* ========== WAKE WORD LISTENER ("Hey Scout") ========== */
    function start_wake_word_listener() {
        var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
            console.log('Wake word: SpeechRecognition not supported');
            return;
        }

        wakeRecognition = new SR();
        wakeRecognition.lang = 'en-US';
        wakeRecognition.continuous = true;
        wakeRecognition.interimResults = true;
        wakeRecognition.maxAlternatives = 3;

        wakeRecognition.onstart = function() {
            wakeListening = true;
            $('#km-wake-status').addClass('km-wake-active').attr('title', 'Listening for "Hey Scout"');
        };

        wakeRecognition.onresult = function(e) {
            // Check recent results for wake phrase
            for (var i = e.resultIndex; i < e.results.length; i++) {
                for (var j = 0; j < e.results[i].length; j++) {
                    var transcript = (e.results[i][j].transcript || '').toLowerCase().trim();
                    var matched = WAKE_PHRASES.some(function(phrase) {
                        return transcript.indexOf(phrase) !== -1;
                    });
                    if (matched) {
                        // Wake word detected!
                        handle_wake_word(transcript);
                        return;
                    }
                }
            }
        };

        wakeRecognition.onerror = function(e) {
            // 'no-speech' and 'aborted' are expected during continuous listening
            if (e.error !== 'no-speech' && e.error !== 'aborted') {
                console.log('Wake word error:', e.error);
            }
        };

        wakeRecognition.onend = function() {
            wakeListening = false;
            $('#km-wake-status').removeClass('km-wake-active');
            // Auto-restart unless STT is actively recording
            if (!isListening) {
                setTimeout(function() {
                    if (!isListening && wakeRecognition) {
                        try { wakeRecognition.start(); } catch(e) {}
                    }
                }, 300);
            }
        };

        // Initial start (may need user gesture first)
        try {
            wakeRecognition.start();
        } catch(e) {
            // Will start after first user interaction with the page
            $(document).one('click keydown', function() {
                setTimeout(function() {
                    if (wakeRecognition && !wakeListening && !isListening) {
                        try { wakeRecognition.start(); } catch(ex) {}
                    }
                }, 500);
            });
        }
    }

    function pause_wake_listener() {
        if (wakeRecognition && wakeListening) {
            try { wakeRecognition.stop(); } catch(e) {}
            wakeListening = false;
        }
    }

    function resume_wake_listener() {
        if (wakeRecognition && !wakeListening && !isListening) {
            setTimeout(function() {
                try { wakeRecognition.start(); } catch(e) {}
            }, 500);
        }
    }

    function handle_wake_word(transcript) {
        // Stop wake listener while we process
        pause_wake_listener();

        // Play a subtle activation chime
        play_activation_chime();

        // Open chat if not open
        if (!chatOpen) toggle_chat();

        // Switch to AI tab
        if (activeTab !== 'ai') switch_tab('ai');

        // Enable auto-speak
        autoSpeak = true;
        $('#km-auto-speak-btn i').removeClass('fa-volume-off').addClass('fa-volume-up');
        $('#km-auto-speak-btn').removeClass('km-auto-speak-off');

        // Check if there's a command after the wake word
        var command = '';
        WAKE_PHRASES.forEach(function(phrase) {
            var idx = transcript.indexOf(phrase);
            if (idx !== -1) {
                command = transcript.substring(idx + phrase.length).trim();
            }
        });

        if (command && command.length > 2) {
            // User said something after "Hey Scout" — send it as a message
            add_bot_message("🎤 I heard you! Processing...", null, true);
            setTimeout(function() {
                send_ai_message(command);
                resume_wake_listener();
            }, 300);
        } else {
            // Just the wake word — greet and start listening for input
            add_bot_message("I'm here! 🐾 What can I help you with?", null, true);
            setTimeout(function() {
                toggle_stt(); // Start recording for Whisper
            }, 600);
        }
    }

    function play_activation_chime() {
        try {
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            // Two-tone chime: E5 then G5
            var notes = [659.25, 783.99];
            notes.forEach(function(freq, i) {
                var osc = ctx.createOscillator();
                var gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = 'sine';
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.12, ctx.currentTime + i * 0.12);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.12 + 0.25);
                osc.start(ctx.currentTime + i * 0.12);
                osc.stop(ctx.currentTime + i * 0.12 + 0.25);
            });
        } catch(e) {}
    }
})();
