from flask import Flask
from workflows_cdk import Router

# Create Flask app
app = Flask(__name__)
router = Router(app)

if __name__ == "__main__":
    router.run_app(app)
