import ivoryos
from flask import Flask, render_template, Blueprint, current_app
import os

# # [access hardware] Comment back this block if need access to control hardware
# # to get the component, user global_config.deck.hardware_name (e.g. global_config.deck.balance)
# from ivoryos.utils.global_config import GlobalConfig
# global_config = GlobalConfig()


# blueprint name Blueprint('plugin', ...) need to be unique and cannot be names that are already registered
# ["auth", "control", "database", "design", "main"] are reserved for ivoryos
plugin = Blueprint("plugin", __name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))


# # [access socketio] this block is for setting socketio, optional
# socketio = None
#
# def init_socketio(sio):
#     """ Attach SocketIO to this plugin """
#     global socketio
#     socketio = sio
#
#     @socketio.on('connect')
#     def handle_connect():
#         pass


# # [main route] the route url can be anything, but "main" is needed as entry point
@plugin.route('/')
def main():
    base_exists = "base.html" in current_app.jinja_loader.list_templates()
    return render_template('example.html', base_exists=base_exists)


if __name__ == '__main__':

    # ------------------------------------------
    # ---- Option 1 - run without websocket ----
    # ------------------------------------------
    app = Flask(__name__)
    app.register_blueprint(plugin)
    app.run()

    # ------------------------------------------
    # ---- Option 2 - run with websocket -------
    # ------------------------------------------
    # app = Flask(__name__)
    # app.register_blueprint(plugin)
    # socketio = SocketIO(app)
    # init_socketio(socketio)
    # socketio.run(app, debug=True, allow_unsafe_werkzeug=True)


    # # ------------------------------------------
    # # ---- Option 3 - run with ivoryos -------
    # # ------------------------------------------
    # ivoryos.run(__name__,blueprint_plugins=plugin)
