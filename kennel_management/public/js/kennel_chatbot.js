/**
 * FurEver Kennel AI Chatbot + Internal Messaging
 * Two tabs: AI Assistant (shelter queries) and Messages (user-to-user DMs)
 */
(function() {
    if (!frappe.session || frappe.session.user === 'Guest') return;

    var chatOpen = false;
    var activeTab = 'ai';
    var dmUser = null;
    var dmPollTimer = null;
    var msgPollTimer = null;
    var unreadCount = 0;

    $(document).ready(function() { build_chat_ui(); });

    /* ========== DOG SVG ========== */
    var dogSVG = `<svg class="km-dog-svg" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
        <!-- tail -->
        <path class="km-dog-tail" d="M10 16 Q4 8, 8 4"/>
        <!-- body -->
        <ellipse class="km-dog-body" cx="24" cy="28" rx="14" ry="12"/>
        <!-- head -->
        <circle class="km-dog-body" cx="36" cy="18" r="10"/>
        <!-- ears -->
        <ellipse class="km-dog-ear" cx="30" cy="9" rx="4" ry="6" transform="rotate(-15 30 9)"/>
        <ellipse class="km-dog-ear" cx="42" cy="11" rx="4" ry="6" transform="rotate(15 42 11)"/>
        <!-- eyes -->
        <circle class="km-dog-eye" cx="33" cy="17" r="1.8"/>
        <circle class="km-dog-eye" cx="40" cy="17" r="1.8"/>
        <!-- nose -->
        <ellipse class="km-dog-nose" cx="37" cy="21" rx="2.2" ry="1.6"/>
        <!-- tongue -->
        <rect class="km-dog-tongue" x="35.5" y="23" width="3" height="4" rx="1.5" transform-origin="37 23"/>
        <!-- legs -->
        <rect class="km-dog-body" x="15" y="36" width="4" height="8" rx="2"/>
        <rect class="km-dog-body" x="23" y="36" width="4" height="8" rx="2"/>
        <rect class="km-dog-body" x="17" y="36" width="4" height="7" rx="2" opacity="0"/>
        <rect class="km-dog-body" x="29" y="36" width="4" height="8" rx="2"/>
    </svg>`;

    /* ========== BUILD UI ========== */
    function build_chat_ui() {
        var fab = $(`<button class="km-chat-fab" title="FurEver Assistant">${dogSVG}<span class="km-fab-badge"></span></button>`);

        var win = $(`
        <div class="km-chat-window" id="km-chat-window">
            <div class="km-chat-header">
                <div class="km-chat-avatar"><i class="fa fa-paw"></i></div>
                <div class="km-chat-hdr-info">
                    <h4>FurEver</h4>
                    <span>Assistant & Team Chat</span>
                </div>
                <button class="km-chat-close"><i class="fa fa-times"></i></button>
            </div>
            <div class="km-chat-tabs">
                <button class="km-chat-tab active" data-tab="ai"><i class="fa fa-magic"></i> Assistant</button>
                <button class="km-chat-tab" data-tab="messages"><i class="fa fa-comments"></i> Messages <span class="km-tab-badge" id="km-msg-badge"></span></button>
            </div>

            <!-- AI Tab -->
            <div class="km-tab-panel active" id="km-panel-ai">
                <div class="km-chat-quick">
                    <button class="km-chat-chip" data-q="How many animals are in the shelter?">Animals</button>
                    <button class="km-chat-chip" data-q="Show today's vet appointments">Vet today</button>
                    <button class="km-chat-chip" data-q="What is the kennel occupancy?">Occupancy</button>
                    <button class="km-chat-chip" data-q="Any pending adoption applications?">Adoptions</button>
                    <button class="km-chat-chip" data-q="Show recent admissions">Intake</button>
                    <button class="km-chat-chip" data-q="Which animals have been waiting longest?">Long stays</button>
                    <button class="km-chat-chip" data-q="Are any kennels full?">Full kennels</button>
                </div>
                <div class="km-chat-messages" id="km-ai-messages"></div>
                <div class="km-chat-input-area">
                    <input class="km-chat-input" id="km-ai-input" placeholder="Ask about the shelter..." autocomplete="off" />
                    <button class="km-chat-send" id="km-ai-send"><i class="fa fa-paper-plane"></i></button>
                </div>
            </div>

            <!-- Messages Tab -->
            <div class="km-tab-panel" id="km-panel-messages">
                <!-- User List View -->
                <div id="km-msg-list-view">
                    <div class="km-user-search">
                        <input type="text" placeholder="Search users..." id="km-user-search-input" />
                    </div>
                    <div class="km-user-list" id="km-user-list">
                        <div class="km-empty-state"><i class="fa fa-comments"></i><p>Loading team...</p></div>
                    </div>
                </div>
                <!-- DM Conversation View -->
                <div id="km-dm-view" style="display:none;flex-direction:column;flex:1;overflow:hidden;">
                    <div class="km-dm-header">
                        <button class="km-dm-back"><i class="fa fa-arrow-left"></i></button>
                        <div class="km-user-avatar km-dm-avatar"></div>
                        <div>
                            <div class="km-dm-name"></div>
                            <div class="km-dm-status">Shelter staff</div>
                        </div>
                    </div>
                    <div class="km-chat-messages" id="km-dm-messages"></div>
                    <div class="km-chat-input-area">
                        <input class="km-chat-input" id="km-dm-input" placeholder="Type a message..." autocomplete="off" />
                        <button class="km-chat-send" id="km-dm-send"><i class="fa fa-paper-plane"></i></button>
                    </div>
                </div>
            </div>

            <div class="km-chat-footer">FurEver Kennel Management</div>
        </div>`);

        $('body').append(fab).append(win);

        // AI welcome
        add_bot_message("Hi! 🐾 I'm your FurEver assistant. Ask me about animals, kennels, appointments, or adoptions.");

        // Events
        fab.on('click', toggle_chat);
        win.find('.km-chat-close').on('click', toggle_chat);

        // Tabs
        win.find('.km-chat-tab').on('click', function() {
            var tab = $(this).data('tab');
            switch_tab(tab);
        });

        // AI events
        win.find('.km-chat-chip').on('click', function() { send_ai_message($(this).data('q')); });
        win.find('#km-ai-send').on('click', function() {
            var msg = $('#km-ai-input').val().trim();
            if (msg) send_ai_message(msg);
        });
        win.find('#km-ai-input').on('keypress', function(e) {
            if (e.which === 13) { var msg = $(this).val().trim(); if (msg) send_ai_message(msg); }
        });

        // DM events
        win.find('#km-dm-send').on('click', function() {
            var msg = $('#km-dm-input').val().trim();
            if (msg && dmUser) send_dm(msg);
        });
        win.find('#km-dm-input').on('keypress', function(e) {
            if (e.which === 13) { var msg = $(this).val().trim(); if (msg && dmUser) send_dm(msg); }
        });
        win.find('.km-dm-back').on('click', close_dm);

        // User search
        win.find('#km-user-search-input').on('input', function() {
            var q = $(this).val().trim().toLowerCase();
            $('#km-user-list .km-user-item').each(function() {
                var name = $(this).data('fullname').toLowerCase();
                $(this).toggle(name.indexOf(q) !== -1);
            });
        });

        // Start polling for unread messages
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

        if (tab === 'messages') {
            load_user_list();
        }
    }

    function toggle_chat() {
        chatOpen = !chatOpen;
        $('#km-chat-window').toggleClass('open', chatOpen);
        if (chatOpen) {
            if (activeTab === 'ai') {
                setTimeout(function() { $('#km-ai-input').focus(); }, 200);
            } else {
                load_user_list();
            }
        }
    }

    /* ========== AI ASSISTANT ========== */
    function add_bot_message(text) {
        var time = frappe.datetime.now_time().substring(0, 5);
        $('#km-ai-messages').append(
            '<div class="km-msg km-msg-bot">' + format_bot_text(text) + '<div class="km-msg-time">' + time + '</div></div>'
        );
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
                    add_bot_message(r.message.reply);
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
                    var user = $(this).data('user');
                    var name = $(this).data('fullname');
                    open_dm(user, name);
                });
            }
        });
    }

    function open_dm(user, fullName) {
        dmUser = user;
        var initial = (fullName || 'U').charAt(0).toUpperCase();
        $('#km-msg-list-view').hide();
        $('#km-dm-view').css('display', 'flex');
        $('.km-dm-name').text(fullName);
        $('.km-dm-avatar').text(initial);
        $('#km-dm-messages').html('<div class="km-empty-state"><i class="fa fa-spinner fa-spin"></i><p>Loading...</p></div>');
        load_dm_messages();
        // Poll for new DMs
        if (dmPollTimer) clearInterval(dmPollTimer);
        dmPollTimer = setInterval(load_dm_messages, 5000);
    }

    function close_dm() {
        dmUser = null;
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
            error: function() {
                frappe.show_alert({message: 'Failed to send message', indicator: 'red'});
            }
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
    function show_typing(containerId) {
        $('#' + containerId).append(
            '<div class="km-typing" id="km-typing"><div class="km-typing-dot"></div><div class="km-typing-dot"></div><div class="km-typing-dot"></div></div>'
        );
        scroll_el(containerId);
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
