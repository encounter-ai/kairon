from fastapi import APIRouter, Security, Path
from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm
from starlette.background import BackgroundTasks
from starlette.requests import Request

from kairon import Utility
from kairon.shared.auth import Authentication
from kairon.api.models import Response
from kairon.shared.constants import ADMIN_ACCESS
from kairon.shared.models import User

router = APIRouter()


@router.post("/login", response_model=Response)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticates the user and generates jwt token
    """
    access_token = Authentication.authenticate(form_data.username, form_data.password)
    return {
        "data": {"access_token": access_token, "token_type": "bearer"},
        "message": "User Authenticated",
    }


@router.get("/{bot}/integration/token", response_model=Response)
async def generate_integration_token(
    current_user: User = Security(Authentication.get_current_user_and_bot, scopes=ADMIN_ACCESS),
):
    """
    Generates an access token for api integration
    """
    access_token = Authentication.generate_integration_token(
        bot=current_user.get_bot(), account=current_user.account
    )
    return {
        "data": {"access_token": access_token, "token_type": "bearer"},
        "message": """It is your responsibility to keep the token secret.
        If leaked then other may have access to your system.""",
    }


@router.get("/login/sso/list/enabled", response_model=Response)
async def sso_enabled_login_list():
    """
    List social media logins enabled.
    """
    return Response(data=Utility.get_enabled_sso())


@router.get('/login/sso/{sso_type}')
async def sso_login(sso_type: str = Path(default=None, description="social media type", example="google")):
    """
    Generate redirect url based on social media type.
    """
    return await Authentication.get_redirect_url(sso_type)


@router.get("/login/sso/callback/{sso_type}", response_model=Response)
async def sso_callback(
        request: Request,
        background_tasks: BackgroundTasks,
        sso_type: str = Path(default=None, description="social media type", example="google")
):
    """
    Generate login token after successful social media login.
    """
    existing_user, user_details, access_token = await Authentication.verify_and_process(request, sso_type)
    if not existing_user and Utility.email_conf["email"]["enable"]:
        background_tasks.add_task(
            Utility.format_and_send_mail, mail_type='password_generated', email=user_details['email'],
            first_name=user_details['first_name'], password=user_details['password'].get_secret_value()
        )
    return {
        "data": {"access_token": access_token, "token_type": "bearer"},
        "message": """It is your responsibility to keep the token secret.
        If leaked then other may have access to your system.""",
    }
