import os
import pymongo
import datetime
from flask import Flask, render_template, url_for, session, redirect,\
    flash, request, Blueprint
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from flask_paginate import Pagination, get_page_parameter


app = Flask(__name__)
mod = Blueprint('users', __name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.getenv('MONGO_URI')
app.secret_key = os.environ.get('SECRET_KEY')

mongo = PyMongo(app)


def pagination_vars():
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10
    offset = (page - 1) * per_page
    search = False
    q = request.args.get('q')
    if q:
        search = True
    return page, per_page, offset, search


@app.route("/")
@app.route("/get_recipes")
def home_page():
    """ displays the home page as well as a list of available recipes"""
    page, per_page, offset, search = pagination_vars()
    recipes = mongo.db.recipes.find().sort(
        'updated_on', pymongo.ASCENDING).limit(per_page).skip(offset)
    pagination = Pagination(page=page, total=recipes.count(), search=search,
                            record_name='recipes', offset=offset)
    return render_template('home_page.html',
                           recipes=list(recipes),
                           header="Check out our latest recipes",
                           pagination=pagination)


@app.route("/about")
def about():
    return render_template('about.html')


@app.route("/recipes/search", methods=["GET", "POST"])
def text_search():
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10
    offset = (page - 1) * per_page
    searchit = False
    q = request.args.get('q')
    if q:
        searchit = True
    search = request.form.get('search')
    recipes = mongo.db.recipes.find({'$text': {'$search': search}}).limit(
        per_page).skip(offset)
    pagination = Pagination(page=page, total=recipes.count(), search=searchit,
                            record_name='recipes', offset=offset)
    print(pagination)
    return render_template('home_page.html', recipes=list(recipes),
                           error_message=f'No recipes match the \
                               search "{search}"', pagination=pagination,
                           header=f"Recipes containing {search}")


@app.context_processor
def get_categories():
    """ returns a dict of categories to be listed in the navbar """
    return dict(categories=mongo.db.categories.find())


@app.route("/user/create_account", methods=["GET"])
def create_account():
    """ displays the create account page/form """
    return render_template('create_account.html')


@app.route("/user/create_account/post", methods=["POST"])
def insert_account():
    """ (from "create_account" submit) checks if the username is already in the
database and if the double entered passwords match, if the username is not
taken and the passwords match, a new user is created in the database """
    existing_user = mongo.db.users.find_one({"user_name": request.form.get(
        'username').lower()})
    if existing_user:
        flash('This username is taken')
        return redirect(url_for('create_account'))
    else:
        if request.form.get('password') == \
                request.form.get('confirm_password'):
            mongo.db.users.insert_one({
                "user_name": request.form.get('username').lower(),
                "email_address": request.form.get('email'),
                "password": generate_password_hash(
                        request.form.get('password'))
            })
            flash("Account Created")
            return redirect(url_for('user_login'))
        else:
            flash("Your passwords didn't match")
            return redirect(url_for('create_account'))


@app.route("/user/login", methods=["GET"])
def user_login():
    """ displays the login page/form """
    return render_template('user_login.html')


@app.route("/user/login/post", methods=["POST"])
def login():
    """ (from "user_login" submit) checks if the username is in the
    database and if so, that the passwords match, if the username is present
    and the passwords match, the user is logged in """
    existing_user = mongo.db.users.find_one({"user_name": request.form.get(
        'username').lower()})
    if existing_user:
        if check_password_hash(existing_user["password"],
                               request.form.get("password")):
            session['username'] = existing_user['user_name']
            return redirect(url_for('home_page'))
        else:
            flash('Incorrect password')
            return redirect(url_for('user_login'))
    else:
        flash('The username you entered does not exist')
        return redirect(url_for('user_login'))
    return render_template('home_page.html', user=mongo.db.users.find_one(
                            {'user_name': request.form.get('username')}))


@app.route('/user/logout')
def logout():
    """ logs user out by removing username from session, redirects
    to home page """
    session.pop('username', None)
    return redirect(url_for('home_page'))


@app.route('/recipes/create_recipe')
def create_recipe():
    """ opens the create recipe page with all the
    input fields to create a new recipe """
    return render_template('create_recipe.html',
                           cats=mongo.db.categories.find())


@app.route("/recipes/create_recipe/post", methods=['POST'])
def insert_recipe():
    """ takes the data from the create_recipe form and creates
    a new doument in the recipes collection to store the data
    (along with the time/date the recipe was created and last edited),
    then redirects the user back to the home page """
    recipes = mongo.db.recipes
    current_time = datetime.datetime.now().strftime('%X %x')
    recipes.insert_one({
        'category': request.form.get('category'),
        'recipe_name': request.form.get('recipe_name'),
        'description': request.form.get('description'),
        'ingredients': request.form.getlist('ingredients'),
        'method': request.form.getlist('method'),
        'required_tools': request.form.getlist('tools'),
        'servings': request.form.get('servings'),
        'preparation_time': request.form.get('preparation_time'),
        'cook_time': request.form.get('cook_time'),
        'image_url': request.form.get("image_url"),
        'created_on': current_time,
        'updated_on': current_time,
        'owner': session['username']
    })
    return redirect(url_for('home_page'))


@app.route('/recipes/search/<category>')
def recipes_by_category(category):
    """ searches for all recipes with a chosen category from a drop down list,
    then displays those recipes on the home page """
    page, per_page, offset, search = pagination_vars()
    recipes = mongo.db.recipes.find({'category': category}).sort(
        'updated_on', pymongo.ASCENDING).limit(per_page).skip(offset)
    pagination = Pagination(page=page, total=recipes.count(), search=search,
                            record_name='recipes', offset=offset)
    return render_template('home_page.html', recipes=list(recipes),
                           header="All " + category.capitalize() + " Recipes",
                           error_message=f"No results for \
                           {category.capitalize()}", pagination=pagination)


@app.route('/recipes/search/<owner>')
def user_recipes(owner):
    """ displays a list of all the recipes created by the current user,
    using the session['username'] variable """
    page, per_page, offset, search = pagination_vars()
    recipes = mongo.db.recipes.find({'owner': session['username']}).sort(
        'updated_on', pymongo.ASCENDING).limit(per_page).skip(offset)
    pagination = Pagination(page=page, total=recipes.count(), search=search,
                            record_name='recipes', offset=offset)
    return render_template('home_page.html', recipes=list(recipes),
                           header="All " + owner.capitalize() + " Recipes",
                           error_message=f"{owner.capitalize()}\
                            currently has no recipes",
                           pagination=pagination)


@app.route('/recipes/view_recipe/<recipe_id>')
def view_recipe(recipe_id):
    """ generates a display of all the information
    related to a particular recipe based on the recipe_id"""
    return render_template('view_recipe.html',
                           recipe=mongo.db.recipes.find_one({
                            '_id': ObjectId(recipe_id)}))


@app.route('/recipes/edit_recipe/<recipe_id>')
def edit_recipe(recipe_id):
    """ displays a form similar to the create_recipe page,
    that is pre-filled with the data from the chosen recipe,
    allowing the user to edit and save the changes
    (this is only visible to the user that created the recipe) """
    return render_template('edit_recipe.html',
                           recipe=mongo.db.recipes.find_one({
                            '_id': ObjectId(recipe_id)}),
                           cats=mongo.db.categories.find())


@app.route('/recipes/update_recipe/<recipe_id>', methods=["POST"])
def update_recipe(recipe_id):
    """ updates a recipe using recipe_id based on the information input into the
    edit_recipe page. The owner and created on fields are not updated and the
    updated_on field is automatically updated """
    current_time = datetime.datetime.now().strftime('%X %x')
    mongo.db.recipes.update({'_id': ObjectId(recipe_id)},
                            {'$set': {
                                'category': request.form.get('category'),
                                'recipe_name': request.form.get('recipe_name'),
                                'description': request.form.get('description'),
                                'ingredients': request.form.getlist(
                                    'ingredients'),
                                'method': request.form.getlist('method'),
                                'required_tools': request.form.getlist(
                                    'tools'),
                                'servings': request.form.get('servings'),
                                'preparation_time': request.form.get(
                                    'preparation_time'),
                                'cook_time': request.form.get('cook_time'),
                                'image_url': request.form.get("image_url"),
                                'updated_on': current_time,
                            }})
    return redirect(url_for('view_recipe', recipe_id=recipe_id))


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)
