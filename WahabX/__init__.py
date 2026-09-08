
#
# All rights reserved.

from WahabX.core.bot import AyuBot
from WahabX.core.dir import dirr
from WahabX.core.git import git
from WahabX.core.userbot import Userbot
from WahabX.misc import dbb, heroku, sudo

from .logging import LOGGER

# Directories
dirr()

# Check Git Updates
git()

# Initialize Memory DB
dbb()

# Heroku APP
heroku()

# Load Sudo Users from DB
sudo()

# Bot Client
app = AyuBot()

# Assistant Client
userbot = Userbot()

from .platforms import PlaTForms

Platform = PlaTForms()
HELPABLE = {}
