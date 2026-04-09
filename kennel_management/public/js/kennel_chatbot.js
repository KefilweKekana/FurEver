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

    // STT state
    var recognition = null;
    var isListening = false;

    $(document).ready(function() { build_chat_ui(); setup_call_listeners(); });

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
        var fab = $('<button class="km-chat-fab" title="FurEver Assistant">' + dogSVG + '<span class="km-fab-badge"></span></button>');

        var win = $([
        '<div class="km-chat-window" id="km-chat-window">',
            '<div class="km-chat-header">',
                '<div class="km-chat-avatar"><i class="fa fa-paw"></i></div>',
                '<div class="km-chat-hdr-info">',
                    '<h4>FurEver</h4>',
                    '<span>Assistant &amp; Team Chat</span>',
                '</div>',
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
                '</div>',
                '<div class="km-chat-messages" id="km-ai-messages"></div>',
                '<div class="km-chat-input-area">',
                    '<button class="km-mic-btn" id="km-mic-btn" title="Voice input"><i class="fa fa-microphone"></i></button>',
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
            '<div class="km-chat-footer">FurEver Kennel Management</div>',
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

        // AI welcome
        add_bot_message("Hi! \ud83d\udc3e I'm your FurEver assistant. Ask me about animals, kennels, appointments, or adoptions. Try asking \"Where is Buddy?\" or \"Who is in Kennel A1?\"");

        // Events
        fab.on('click', toggle_chat);
        win.find('.km-chat-close').on('click', toggle_chat);
        win.find('.km-chat-tab').on('click', function() { switch_tab($(this).data('tab')); });

        // AI events
        win.find('.km-chat-chip').on('click', function() { send_ai_message($(this).data('q')); });
        win.find('#km-ai-send').on('click', function() {
            var msg = $('#km-ai-input').val().trim();
            if (msg) send_ai_message(msg);
        });
        win.find('#km-ai-input').on('keypress', function(e) {
            if (e.which === 13) { var msg = $(this).val().trim(); if (msg) send_ai_message(msg); }
        });

        // Mic button
        win.find('#km-mic-btn').on('click', toggle_stt);

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

    /* ========== AI ASSISTANT ========== */
    function add_bot_message(text, animals) {
        var time = frappe.datetime.now_time().substring(0, 5);
        var msgHtml = '<div class="km-msg km-msg-bot">'
            + format_bot_text(text)
            + '<div class="km-msg-time">' + time
            + ' <button class="km-tts-btn" title="Listen"><i class="fa fa-volume-up"></i></button>'
            + '</div></div>';
        $('#km-ai-messages').append(msgHtml);

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
    }

    function add_user_ai_message(text) {
        var time = frappe.datetime.now_time().substring(0, 5);
        $('#km-ai-messages').append(
            '<div class="km-msg km-msg-user">' + frappe.utils.escape_html(text) + '<div class="km-msg-time">' + time + '</div></div>'
        );
        scroll_el('km-ai-messages');
    }

    function send_ai_message(text) {
        add_user_ai_message(text);
        $('#km-ai-input').val('');
        $('#km-ai-send').prop('disabled', true);
        show_typing('km-ai-messages');

        frappe.call({
            method: 'kennel_management.api.chatbot_query',
            args: { message: text },
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

    /* ========== TEXT-TO-SPEECH ========== */
    function speak_text(text) {
        if (!speechSynth) {
            frappe.show_alert({message: 'Text-to-speech not supported', indicator: 'orange'});
            return;
        }
        speechSynth.cancel();
        var cleaned = text.replace(/\*\*(.*?)\*\*/g, '$1').replace(/[•\n]/g, '. ').replace(/\s+/g, ' ').trim();
        var utter = new SpeechSynthesisUtterance(cleaned);
        utter.rate = 1.0;
        utter.pitch = 1.0;
        var voices = speechSynth.getVoices();
        var pref = voices.find(function(v) { return v.lang.startsWith('en') && v.name.indexOf('Female') > -1; })
            || voices.find(function(v) { return v.lang.startsWith('en-US'); })
            || voices.find(function(v) { return v.lang.startsWith('en'); });
        if (pref) utter.voice = pref;
        speechSynth.speak(utter);
    }

    /* ========== SPEECH-TO-TEXT ========== */
    function toggle_stt() {
        if (isListening) { stop_stt(); return; }
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
            if (t.trim()) send_ai_message(t.trim());
        };
        recognition.onerror = function() { stop_stt(); };
        recognition.onend = function() { stop_stt(); };
        recognition.start();
    }

    function stop_stt() {
        isListening = false;
        $('#km-mic-btn').removeClass('km-mic-active');
        if (recognition) { try { recognition.stop(); } catch(e) {} recognition = null; }
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
    function show_typing(id) {
        $('#' + id).append('<div class="km-typing" id="km-typing"><div class="km-typing-dot"></div><div class="km-typing-dot"></div><div class="km-typing-dot"></div></div>');
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
})();
