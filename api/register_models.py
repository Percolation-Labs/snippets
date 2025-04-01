"""Register all models that we use
To query models and update models we use this format

import percolate as p8
repo = p8.repository(SomeModel)

repo.get_by_id -> returns a dictionary list at the moment and we can create the model from this
repo.update_records(model or list of models)
repo.select(field=value, other_field=ListOfValues)

"""

from app.models.user import Users
from app.models.payment import Product,Subscription

import percolate as p8


for model in [Users,Product,Subscription]:
    
    p8.repository(model).register()