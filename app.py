from flask import Flask
from flask_graphql import GraphQLView
import graphene
from graphqlbackend import Query
from flask_cors import CORS
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask application
application = Flask(__name__)

# CORS configuration (adjust origins as needed)
CORS(application, resources={r"/graphql": {"origins": "*"}})

# Define GraphQL view
view_func = GraphQLView.as_view(
    'graphql', 
    schema=graphene.Schema(query=Query), 
    graphiql=True
)
application.add_url_rule('/graphql', view_func=view_func)

if __name__ == '__main__':
    # Run the application
    application.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
