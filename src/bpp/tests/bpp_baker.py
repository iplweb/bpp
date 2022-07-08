from model_bakery import baker


class BPP_Baker(baker.Baker):
    def get_fields(self):
        # Model Bakery nie może podawać tych parametrów dla modeli MPTT
        # https://stackoverflow.com/questions/32267084/model-mommy-breaks-django-mptt

        return [
            field
            for field in super(BPP_Baker, self).get_fields()
            if field.name not in ["lft", "rght"]
        ]
