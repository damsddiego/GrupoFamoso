/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";

patch(Chatter.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.globalRestrictions = {};
        this.currentRestrictions = {}; // Reintroduced currentRestrictions for model-specific checks

        onWillStart(async () => {
            try {
                const { model_restrictions } = await this.orm.call(
                    "sh.hide.chatter",
                    "sh_checkhide_chatter",
                    [{ user_id: user.userId }]
                );
                this.globalRestrictions = model_restrictions["global"] || {}; // Use only global restrictions
                this.currentRestrictions = model_restrictions[this.props.threadModel] || {}; // Model-specific restrictions
            } catch (error) {
            }
        });
    },

    // -------------------------------------------------
    // Checks Global hide or model-specific hide applies
    // -------------------------------------------------

    isSHChatterHidden() {
        
        return this.globalRestrictions.sh_global_hide_full_chatter || this.currentRestrictions.hide_full_chatter || false;
    },

    isSHSendMessageHidden() {
        return this.globalRestrictions.sh_global_hide_send_message || this.currentRestrictions.hide_send_msg || false;
    },

    isSHLogNoteHidden() {
        return this.globalRestrictions.sh_global_hide_log_note || this.currentRestrictions.hide_log_notes || false;
    },

    isSHActivityHidden() {
        return this.globalRestrictions.sh_global_hide_activity || this.currentRestrictions.hide_activity || false;
    },

    isSHSearchMessageIconHidden() {
        return this.globalRestrictions.sh_global_hide_search_message_icon || false;
    },

    isSHAttachmentIconHidden() {
        return this.globalRestrictions.sh_global_hide_attachment_icon || false;
    },

    isSHFollowersIconHidden() {
        return this.globalRestrictions.sh_global_hide_followers_icon || false;
    },

    isSHFollowUnfollowButtonHidden() {
        return this.globalRestrictions.sh_global_hide_follow_unfollow_button || false;
    },
});