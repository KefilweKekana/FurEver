/**
 * FurEver Kennel AI Chatbot
 * Internal assistant for shelter staff — queries shelter data and optionally uses AI.
 */
(function() {
    if (!frappe.session || frappe.session.user === 'Guest') return;

    var chatOpen = false;
    var messages = [];

    // Build UI on page ready
    $(document).ready(function() {
        build_chat_ui();
    });

    function build_chat_ui() {
        // Floating action button
        var fab = $(`
            <button class="km-chat-fab" title="FurEver Assistant">
                <i class="fa fa-commenting"></i>
                <span class="km-fab-badge"></span>
            </button>
        `);

        // Chat window
        var win = $(`
            <div class="km-chat-window" id="km-chat-window">
                <div class="km-chat-header">
                    <div class="km-chat-avatar"><i class="fa fa-paw"></i></div>
                    <div class="km-chat-title">
                        <h4>FurEver Assistant</h4>
                        <span>AI-powered shelter helper</span>
                    </div>
                    <button class="km-chat-close"><i class="fa fa-times"></i></button>
                </div>
                <div class="km-chat-quick">
                    <button class="km-chat-chip" data-q="How many animals are in the shelter?">Animals count</button>
                    <button class="km-chat-chip" data-q="Show today's vet appointments">Vet today</button>
                    <button class="km-chat-chip" data-q="What is the kennel occupancy?">Occupancy</button>
                    <button class="km-chat-chip" data-q="Any pending adoption applications?">Pending apps</button>
                    <button class="km-chat-chip" data-q="Show recent admissions">Recent intake</button>
                </div>
                <div class="km-chat-messages" id="km-chat-messages"></div>
                <div class="km-chat-input-area">
                    <input class="km-chat-input" id="km-chat-input" placeholder="Ask about the shelter..." autocomplete="off" />
                    <button class="km-chat-send" id="km-chat-send"><i class="fa fa-paper-plane"></i></button>
                </div>
                <div class="km-chat-footer">Powered by FurEver AI</div>
            </div>
        `);

        $('body').append(fab).append(win);

        // Welcome message
        add_bot_message("Hi there! 👋 I'm your FurEver shelter assistant. Ask me anything about animals, kennels, appointments, or adoptions.");

        // Events
        fab.on('click', toggle_chat);
        win.find('.km-chat-close').on('click', toggle_chat);

        win.find('.km-chat-chip').on('click', function() {
            var q = $(this).data('q');
            send_message(q);
        });

        var input = win.find('#km-chat-input');
        var sendBtn = win.find('#km-chat-send');

        sendBtn.on('click', function() {
            var msg = input.val().trim();
            if (msg) send_message(msg);
        });

        input.on('keypress', function(e) {
            if (e.which === 13) {
                var msg = input.val().trim();
                if (msg) send_message(msg);
            }
        });
    }

    function toggle_chat() {
        chatOpen = !chatOpen;
        $('#km-chat-window').toggleClass('open', chatOpen);
        if (chatOpen) {
            setTimeout(function() { $('#km-chat-input').focus(); }, 200);
        }
    }

    function add_bot_message(text) {
        var time = frappe.datetime.now_time().substring(0, 5);
        var html = '<div class="km-msg km-msg-bot">'
            + format_bot_text(text)
            + '<div class="km-msg-time">' + time + '</div></div>';
        $('#km-chat-messages').append(html);
        scroll_bottom();
    }

    function add_user_message(text) {
        var time = frappe.datetime.now_time().substring(0, 5);
        var html = '<div class="km-msg km-msg-user">'
            + frappe.utils.escape_html(text)
            + '<div class="km-msg-time">' + time + '</div></div>';
        $('#km-chat-messages').append(html);
        scroll_bottom();
    }

    function show_typing() {
        var el = $('<div class="km-typing" id="km-typing">'
            + '<div class="km-typing-dot"></div>'
            + '<div class="km-typing-dot"></div>'
            + '<div class="km-typing-dot"></div></div>');
        $('#km-chat-messages').append(el);
        scroll_bottom();
    }

    function hide_typing() {
        $('#km-typing').remove();
    }

    function scroll_bottom() {
        var el = document.getElementById('km-chat-messages');
        if (el) el.scrollTop = el.scrollHeight;
    }

    function format_bot_text(text) {
        // Bold: **text**
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Line breaks
        text = text.replace(/\n/g, '<br>');
        return text;
    }

    function send_message(text) {
        add_user_message(text);
        $('#km-chat-input').val('');
        $('#km-chat-send').prop('disabled', true);
        show_typing();

        frappe.call({
            method: 'kennel_management.api.chatbot_query',
            args: { message: text },
            callback: function(r) {
                hide_typing();
                $('#km-chat-send').prop('disabled', false);
                if (r.message) {
                    add_bot_message(r.message.reply);
                    if (r.message.actions && r.message.actions.length) {
                        render_actions(r.message.actions);
                    }
                } else {
                    add_bot_message("Sorry, I couldn't process that. Please try again.");
                }
            },
            error: function() {
                hide_typing();
                $('#km-chat-send').prop('disabled', false);
                add_bot_message("Something went wrong. Please try again later.");
            }
        });
    }

    function render_actions(actions) {
        var html = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px;">';
        actions.forEach(function(a) {
            html += '<a href="' + a.route + '" style="font-size:12px;color:#6366f1;font-weight:500;text-decoration:underline;">'
                + frappe.utils.escape_html(a.label) + '</a>';
        });
        html += '</div>';
        var container = $('#km-chat-messages');
        container.children().last().append(html);
        scroll_bottom();
    }
})();
