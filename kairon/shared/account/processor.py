from datetime import datetime
from typing import Dict, Text

from loguru import logger as logging
from mongoengine.errors import DoesNotExist
from mongoengine.errors import ValidationError
from pydantic import SecretStr
from validators import ValidationFailure
from validators import email as mail_check
from kairon.exceptions import AppException
from kairon.shared.account.data_objects import Account, User, Bot, UserEmailConfirmation, Feedback, UiConfig, \
    MailTemplates, SystemProperties, BotAccess
from kairon.shared.actions.data_objects import FormValidationAction, SlotSetAction, EmailActionConfig
from kairon.shared.data.constant import ACCESS_ROLES, ACTIVITY_STATUS
from kairon.shared.data.data_objects import BotSettings, ChatClientConfig, SlotMapping
from kairon.shared.utils import Utility

Utility.load_email_configuration()


class AccountProcessor:

    @staticmethod
    def add_account(name: str, user: str):
        """
        adds a new account

        :param name: account name
        :param user: user id
        :return: account id
        """
        if Utility.check_empty_string(name):
            raise AppException("Account Name cannot be empty or blank spaces")
        Utility.is_exist(
            Account,
            exp_message="Account name already exists!",
            name__iexact=name,
            status=True,
        )
        license = {"bots": 2, "intents": 3, "examples": 20, "training": 3, "augmentation": 5}
        return Account(name=name.strip(), user=user, license=license).save().to_mongo().to_dict()

    @staticmethod
    def get_account(account: int):
        """
        fetch account object

        :param account: account id
        :return: account details
        """
        try:
            account = Account.objects().get(id=account).to_mongo().to_dict()
            return account
        except:
            raise DoesNotExist("Account does not exists")

    @staticmethod
    def add_bot(name: str, account: int, user: str, is_new_account: bool = False):
        """
        add a bot to account

        :param name: bot name
        :param account: account id
        :param user: user id
        :param is_new_account: True if it is a new account
        :return: bot id
        """
        from kairon.shared.data.processor import MongoProcessor
        from kairon.shared.data.data_objects import BotSettings

        if Utility.check_empty_string(name):
            raise AppException("Bot Name cannot be empty or blank spaces")

        if Utility.check_empty_string(user):
            raise AppException("user cannot be empty or blank spaces")

        Utility.is_exist(
            Bot,
            exp_message="Bot already exists!",
            name__iexact=name,
            account=account,
            status=True,
        )
        bot = Bot(name=name, account=account, user=user).save().to_mongo().to_dict()
        bot_id = bot['_id'].__str__()
        if not is_new_account:
            AccountProcessor.allow_access_to_bot(bot_id, user, user, account, ACCESS_ROLES.ADMIN.value, ACTIVITY_STATUS.ACTIVE.value)
        BotSettings(bot=bot_id, user=user).save()
        processor = MongoProcessor()
        config = processor.load_config(bot_id)
        processor.add_or_overwrite_config(config, bot_id, user)
        processor.add_default_fallback_data(bot_id, user, True, True)
        return bot

    @staticmethod
    def list_bots(account_id: int):
        for bot in Bot.objects(account=account_id, status=True):
            bot = bot.to_mongo().to_dict()
            bot.pop('status')
            bot['_id'] = bot['_id'].__str__()
            yield bot

    @staticmethod
    def update_bot(name: Text, bot: Text):
        if Utility.check_empty_string(name):
            raise AppException('Name cannot be empty')
        try:
            bot_info = Bot.objects(id=bot, status=True).get()
            bot_info.name = name
            bot_info.save()
        except DoesNotExist:
            raise AppException('Bot not found')

    @staticmethod
    def delete_bot(bot: Text, user: Text):
        from kairon.shared.data.data_objects import Intents, Responses, Stories, Configs, Endpoints, Entities, \
            EntitySynonyms, Forms, LookupTables, ModelDeployment, ModelTraining, RegexFeatures, Rules, SessionConfigs, \
            Slots, TrainingDataGenerator, TrainingExamples
        from kairon.shared.test.data_objects import ModelTestingLogs
        from kairon.shared.importer.data_objects import ValidationLogs
        from kairon.shared.actions.data_objects import HttpActionConfig, ActionServerLogs, Actions

        try:
            bot_info = Bot.objects(id=bot, status=True).get()
            bot_info.status = False
            bot_info.save()
            Utility.hard_delete_document([
                Actions, BotAccess, BotSettings, Configs, ChatClientConfig, Endpoints, Entities, EmailActionConfig,
                EntitySynonyms, Forms, FormValidationAction, HttpActionConfig, Intents, LookupTables, RegexFeatures,
                Responses, Rules, SlotMapping, SlotSetAction, SessionConfigs, Slots, Stories, TrainingDataGenerator,
                TrainingExamples, ActionServerLogs, ModelTraining, ModelTestingLogs, ModelDeployment, ValidationLogs
            ], bot, user=user)
            AccountProcessor.remove_bot_access(bot)
        except DoesNotExist:
            raise AppException('Bot not found')

    @staticmethod
    def fetch_role_for_user(email: Text, bot: Text):
        try:
            return BotAccess.objects(accessor_email=email, bot=bot,
                                     status=ACTIVITY_STATUS.ACTIVE.value).get().to_mongo().to_dict()
        except DoesNotExist as e:
            logging.error(e)
            raise AppException('Access to bot is denied')

    @staticmethod
    def get_accessible_bot_details(account_id: int, email: Text):
        shared_bots = []
        account_bots = list(AccountProcessor.list_bots(account_id))
        for bot in BotAccess.objects(accessor_email=email, bot_account__ne=account_id,
                                     status=ACTIVITY_STATUS.ACTIVE.value):
            bot_details = AccountProcessor.get_bot(bot['bot'])
            bot_details.pop('status')
            bot_details['_id'] = bot_details['_id'].__str__()
            shared_bots.append(bot_details)
        return {
            'account_owned': account_bots,
            'shared': shared_bots
        }

    @staticmethod
    def allow_bot_and_generate_invite_url(bot: Text, email: Text, user: Text, bot_account: int,
                                          role: ACCESS_ROLES = ACCESS_ROLES.TESTER.value):
        bot_details = AccountProcessor.allow_access_to_bot(bot, email, user, bot_account, role)
        if Utility.email_conf["email"]["enable"]:
            token = Utility.generate_token(email)
            link = f'{Utility.email_conf["app"]["url"]}/{bot}/invite/accept/{token}'
            return bot_details['name'], link

    @staticmethod
    def allow_access_to_bot(bot: Text, accessor_email: Text, user: Text,
                            bot_account: int, role: ACCESS_ROLES = ACCESS_ROLES.TESTER.value,
                            activity_status: ACTIVITY_STATUS = ACTIVITY_STATUS.INVITE_NOT_ACCEPTED.value):
        """
        Adds bot to a user account.

        :param bot: bot id
        :param accessor_email: email id of the new member
        :param user: user adding the new member
        :param bot_account: account where bot exists
        :param activity_status: can be one of active, inactive or deleted.
        :param role: can be one of admin, designer or tester.
        """
        bot_details = AccountProcessor.get_bot(bot)
        Utility.is_exist(BotAccess, 'User is already a collaborator', accessor_email=accessor_email, bot=bot,
                         status__ne=ACTIVITY_STATUS.DELETED.value)
        BotAccess(
            accessor_email=accessor_email,
            bot=bot,
            role=role,
            user=user,
            bot_account=bot_account,
            status=activity_status
        ).save()
        return bot_details

    @staticmethod
    def update_bot_access(bot: Text, accessor_email: Text, user: Text,
                          role: ACCESS_ROLES = ACCESS_ROLES.TESTER.value,
                          status: ACTIVITY_STATUS = ACTIVITY_STATUS.ACTIVE.value):
        """
        Adds bot to a user account.

        :param bot: bot id
        :param accessor_email: email id of the new member
        :param user: user adding the new member
        :param role: can be one of admin, designer or tester.
        :param status: can be one of active, inactive or deleted.
        """
        AccountProcessor.get_bot(bot)
        try:
            bot_access = BotAccess.objects(accessor_email=accessor_email, bot=bot).get()
            if Utility.email_conf["email"]["enable"]:
                if status != ACTIVITY_STATUS.DELETED.value and bot_access.status == ACTIVITY_STATUS.INVITE_NOT_ACCEPTED.value:
                    raise AppException('User is yet to accept the invite')
            bot_access.role = role
            bot_access.user = user
            bot_access.status = status
            bot_access.timestamp = datetime.utcnow()
            bot_access.save()
        except DoesNotExist:
            raise AppException('User not yet invited to collaborate')

    @staticmethod
    def accept_bot_access_invite(token: Text, bot: Text):
        """
        Activate user's access to bot.

        :param token: token sent in the link
        :param bot: bot id
        """
        bot_details = AccountProcessor.get_bot(bot)
        accessor_email = Utility.verify_token(token)
        AccountProcessor.get_user_details(accessor_email)
        try:
            bot_access = BotAccess.objects(accessor_email=accessor_email, bot=bot,
                                           status=ACTIVITY_STATUS.INVITE_NOT_ACCEPTED.value).get()
            bot_access.status = ACTIVITY_STATUS.ACTIVE.value
            bot_access.accept_timestamp = datetime.utcnow()
            bot_access.save()
            return bot_access.user, bot_details['name'], bot_access.accessor_email, bot_access.role
        except DoesNotExist:
            raise AppException('No pending invite found for this bot and user')

    @staticmethod
    def remove_bot_access(bot: Text, **kwargs):
        """
        Removes bot from either for all users or only for user supplied.

        :param bot: bot id
        :param kwargs: can be either account or email.
        """
        if kwargs:
            if not Utility.is_exist(BotAccess, None, False, **kwargs, bot=bot, status__ne=ACTIVITY_STATUS.DELETED.value):
                raise AppException('User not a collaborator to this bot')
            active_bot_access = BotAccess.objects(**kwargs, bot=bot, status__ne=ACTIVITY_STATUS.DELETED.value)
        else:
            active_bot_access = BotAccess.objects(bot=bot, status__ne=ACTIVITY_STATUS.DELETED.value)
        active_bot_access.update(set__status=ACTIVITY_STATUS.DELETED.value)

    @staticmethod
    def list_bot_accessors(bot: Text):
        """
        List users who have access to bot.

        :param bot: bot id
        """
        for accessor in BotAccess.objects(bot=bot, status__ne=ACTIVITY_STATUS.DELETED.value):
            accessor = accessor.to_mongo().to_dict()
            accessor['_id'] = accessor['_id'].__str__()
            yield accessor

    @staticmethod
    def get_bot(id: str):
        """
        fetches bot details

        :param id: bot id
        :return: bot details
        """
        try:
            return Bot.objects().get(id=id).to_mongo().to_dict()
        except:
            raise DoesNotExist("Bot does not exists!")

    @staticmethod
    def add_user(
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        account: int,
        user: str,
        is_integration_user=False
    ):
        """
        adds new user to the account

        :param email: user login id
        :param password: user password
        :param first_name: user firstname
        :param last_name:  user lastname
        :param account: account id
        :param user: user id
        :param is_integration_user: is this
        :return: user details
        """
        if (
            Utility.check_empty_string(email)
            or Utility.check_empty_string(last_name)
            or Utility.check_empty_string(first_name)
            or Utility.check_empty_string(password)
        ):
            raise AppException(
                "Email, FirstName, LastName and password cannot be empty or blank spaces"
            )

        Utility.is_exist(
            User,
            exp_message="User already exists! try with different email address.",
            email__iexact=email.strip(),
            status=True,
        )
        return (
            User(
                email=email.strip(),
                password=Utility.get_password_hash(password.strip()),
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                account=account,
                user=user.strip(),
                is_integration_user=is_integration_user,
            )
            .save()
            .to_mongo()
            .to_dict()
        )

    @staticmethod
    def get_user(email: str):
        """
        fetch user details

        :param email: user login id
        :return: user details
        """
        try:
            return User.objects().get(email=email).to_mongo().to_dict()
        except Exception as e:
            logging.error(e)
            raise DoesNotExist("User does not exist!")

    @staticmethod
    def get_user_details(email: str):
        """
        fetches complete user details, checks for whether it is inactive

        :param email: login id
        :return: dict
        """
        user = AccountProcessor.get_user(email)
        if not user["is_integration_user"]:
            AccountProcessor.check_email_confirmation(user["email"])
        if not user["status"]:
            raise ValidationError("Inactive User please contact admin!")
        account = AccountProcessor.get_account(user["account"])
        if not account["status"]:
            raise ValidationError("Inactive Account Please contact system admin!")
        return user

    @staticmethod
    def get_complete_user_details(email: str):
        """
        fetches complete user details including account and bot

        :param email: login id
        :return: dict
        """
        user = AccountProcessor.get_user(email)
        account = AccountProcessor.get_account(user["account"])
        bots = AccountProcessor.get_accessible_bot_details(user["account"], email)
        user["account_name"] = account["name"]
        user['bots'] = bots
        user["_id"] = user["_id"].__str__()
        user.pop('password')
        return user

    @staticmethod
    def get_integration_user(bot: str, account: int):
        """
        creates integration user if it does not exist

        :param bot: bot id
        :param account: account id
        :return: dict
        """
        email = f"{bot}@integration.com"
        if not Utility.is_exist(
            User, raise_error=False, email=email, is_integration_user=True, status=True
        ):
            password = Utility.generate_password()
            user_details = AccountProcessor.add_user(
                email=email,
                password=password,
                first_name=bot,
                last_name=bot,
                account=account,
                user="auto_gen",
                is_integration_user=True,
            )
            AccountProcessor.allow_access_to_bot(bot, email.strip(), "auto_gen", account,
                                                 ACCESS_ROLES.ADMIN.value, ACTIVITY_STATUS.ACTIVE.value)
            return user_details
        else:
            return (
                User.objects(email=email).get(is_integration_user=True).to_mongo().to_dict()
            )

    @staticmethod
    async def account_setup(account_setup: Dict, user: Text):
        """
        create new account

        :param account_setup: dict of account details
        :param user: user id
        :return: dict user details, user email id, confirmation mail subject, mail body
        """
        from kairon.shared.data.processor import MongoProcessor

        account = None
        bot = None
        mail_to = None
        email_enabled = Utility.email_conf["email"]["enable"]
        link = None
        try:
            account = AccountProcessor.add_account(account_setup.get("account"), user)
            bot = AccountProcessor.add_bot('Hi-Hello', account["_id"], user, True)
            user_details = AccountProcessor.add_user(
                email=account_setup.get("email"),
                first_name=account_setup.get("first_name"),
                last_name=account_setup.get("last_name"),
                password=account_setup.get("password").get_secret_value(),
                account=account["_id"].__str__(),
                user=user
            )
            AccountProcessor.allow_access_to_bot(bot["_id"].__str__(), account_setup.get("email"),
                                                 account_setup.get("email"), account['_id'],
                                                 ACCESS_ROLES.ADMIN.value, ACTIVITY_STATUS.ACTIVE.value)
            await MongoProcessor().save_from_path(
                "template/use-cases/Hi-Hello", bot["_id"].__str__(), user="sysadmin"
            )
            if email_enabled:
                token = Utility.generate_token(account_setup.get("email"))
                link = Utility.email_conf["app"]["url"] + '/verify/' + token
                mail_to = account_setup.get("email")

        except Exception as e:
            if account and "_id" in account:
                Account.objects().get(id=account["_id"]).delete()
            if bot and "_id" in bot:
                Bot.objects().get(id=bot["_id"]).delete()
            raise e

        return user_details, mail_to, link

    @staticmethod
    async def default_account_setup():
        """
        default account for testing/demo purposes

        :return: user details
        :raises: if account already exist
        """
        account = {
            "account": "DemoAccount",
            "bot": "Demo",
            "email": "test@demo.in",
            "first_name": "Test_First",
            "last_name": "Test_Last",
            "password": SecretStr("Changeit@123"),
        }
        try:
            user, mail, link = await AccountProcessor.account_setup(account, user="sysadmin")
            return user, mail, link
        except Exception as e:
            logging.info(str(e))

    @staticmethod
    def load_system_properties():
        try:
            system_properties = SystemProperties.objects().get().to_mongo().to_dict()
        except DoesNotExist:
            mail_templates = MailTemplates(
                password_reset=open('template/emails/passwordReset.html', 'r').read(),
                password_reset_confirmation=open('template/emails/passwordResetConfirmation.html', 'r').read(),
                verification=open('template/emails/verification.html', 'r').read(),
                verification_confirmation=open('template/emails/verificationConfirmation.html', 'r').read(),
                add_member_invitation=open('template/emails/memberAddAccept.html', 'r').read(),
                add_member_confirmation=open('template/emails/memberAddConfirmation.html', 'r').read(),
                password_generated=open('template/emails/passwordGenerated.html', 'r').read(),
            )
            system_properties = SystemProperties(mail_templates=mail_templates).save().to_mongo().to_dict()
        Utility.email_conf['email']['templates']['verification'] = system_properties['mail_templates']['verification']
        Utility.email_conf['email']['templates']['verification_confirmation'] = system_properties['mail_templates']['verification_confirmation']
        Utility.email_conf['email']['templates']['password_reset'] = system_properties['mail_templates']['password_reset']
        Utility.email_conf['email']['templates']['password_reset_confirmation'] = system_properties['mail_templates']['password_reset_confirmation']
        Utility.email_conf['email']['templates']['add_member_invitation'] = system_properties['mail_templates']['add_member_invitation']
        Utility.email_conf['email']['templates']['add_member_confirmation'] = system_properties['mail_templates']['add_member_confirmation']
        Utility.email_conf['email']['templates']['password_generated'] = system_properties['mail_templates']['password_generated']

    @staticmethod
    async def confirm_email(token: str):
        """
        Confirms the user through link and updates the database

        :param token: the token from link
        :return: mail id, subject of mail, body of mail
        """
        email_confirm = Utility.verify_token(token)
        Utility.is_exist(
            UserEmailConfirmation,
            exp_message="Email already confirmed!",
            email__iexact=email_confirm.strip(),
        )
        confirm = UserEmailConfirmation()
        confirm.email = email_confirm
        confirm.save()
        user = AccountProcessor.get_user(email_confirm)
        return email_confirm, user['first_name']


    @staticmethod
    def is_user_confirmed(email: str):
        """
        Checks if user is verified and raises an Exception if not

        :param email: mail id of user
        :return: None
        """
        if not Utility.is_exist(UserEmailConfirmation, email__iexact=email.strip(), raise_error=False):
            raise AppException("Please verify your mail")

    @staticmethod
    def check_email_confirmation(email: str):
        """
        Checks if the account is verified through mail

        :param email: email of the user
        :return: None
        """
        email_enabled = Utility.email_conf["email"]["enable"]

        if email_enabled:
            AccountProcessor.is_user_confirmed(email)

    @staticmethod
    async def send_reset_link(mail: str):
        """
        Sends a password reset link to the mail id

        :param mail: email id of the user
        :return: mail id, mail subject, mail body
        """
        email_enabled = Utility.email_conf["email"]["enable"]

        if email_enabled:
            if isinstance(mail_check(mail), ValidationFailure):
                raise AppException("Please enter valid email id")
            if not Utility.is_exist(User, email__iexact=mail.strip(), raise_error=False):
                raise AppException("Error! There is no user with the following mail id")
            if not Utility.is_exist(UserEmailConfirmation, email__iexact=mail.strip(), raise_error=False):
                raise AppException("Error! The following user's mail is not verified")
            token = Utility.generate_token(mail)
            user = AccountProcessor.get_user(mail)
            link = Utility.email_conf["app"]["url"] + '/reset_password/' + token
            return mail, user['first_name'], link
        else:
            raise AppException("Error! Email verification is not enabled")

    @staticmethod
    async def overwrite_password(token: str, password: str):
        """
        Changes the user's password

        :param token: unique token from the password reset page
        :param password: new password entered by the user
        :return: mail id, mail subject and mail body
        """
        if Utility.check_empty_string(password):
            raise AppException("password cannot be empty or blank")
        email = Utility.verify_token(token)
        user = User.objects().get(email=email)
        user.password = Utility.get_password_hash(password.strip())
        user.user = email
        user.password_changed = datetime.utcnow
        user.save()
        return email, user.first_name

    @staticmethod
    async def send_confirmation_link(mail: str):
        """
        Sends a link to the user's mail id for account verification

        :param mail: the mail id of the user
        :return: mail id, mail subject and mail body
        """
        email_enabled = Utility.email_conf["email"]["enable"]

        if email_enabled:
            if isinstance(mail_check(mail), ValidationFailure):
                raise AppException("Please enter valid email id")
            Utility.is_exist(UserEmailConfirmation, exp_message="Email already confirmed!", email__iexact=mail.strip())
            if not Utility.is_exist(User, email__iexact=mail.strip(), raise_error=False):
                raise AppException("Error! There is no user with the following mail id")
            user = AccountProcessor.get_user(mail)
            token = Utility.generate_token(mail)
            link = Utility.email_conf["app"]["url"] + '/verify/' + token
            return mail, user['first_name'], link
        else:
            raise AppException("Error! Email verification is not enabled")

    @staticmethod
    def add_feedback(rating: float, user: str, scale: float = 5.0, feedback: str = None):
        """
        Add user feedback.
        @param rating: user given rating.
        @param user: Kairon username.
        @param scale: Scale on which rating is given. %.0 is the default value.
        @param feedback: feedback if any.
        @return:
        """
        Feedback(rating=rating, scale=scale, feedback=feedback, user=user).save()

    @staticmethod
    def update_ui_config(config: dict, user: str):
        """
        Adds UI configuration such as themes, layout type, flags for stepper
        to render UI components based on it.
        @param config: UI configuration to save.
        @param user: username
        """
        try:
            ui_config = UiConfig.objects(user=user).get()
        except DoesNotExist:
            ui_config = UiConfig(user=user)
        ui_config.config = config
        ui_config.save()

    @staticmethod
    def get_ui_config(user: str):
        """
        Retrieves UI configuration such as themes, layout type, flags for stepper
        to render UI components based on it.
        @param user: username
        """
        try:
            ui_config = UiConfig.objects(user=user).get()
            config = ui_config.config
        except DoesNotExist:
            config = {}
            AccountProcessor.update_ui_config(config, user)
        return config
