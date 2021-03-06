"""
User Validate information functions

Created by Hangyu Fan, May 6, 2018

Last modified: May 8, 2018
"""
from base.exceptions import *
from rest_framework.exceptions import ValidationError
from usersys.models import UserValidate, UserValidateArea, UserValidatePhoto
from usersys.models.user_enum import validate_status_choice
from .utils.usersid import user_from_sid
from usersys.serializers.validate import UserValidateUserSerializer, UserValidateAreaSerializer
from usersys.forms import ValidatePhotoUploadForm


@default_exception(Error500)
@user_from_sid(Error404)
def get_validate_photo(user, t_photo):
    """
    Get photo of validation
    :param user: user object
    :param t_photo: type of photo.
    :return: Path of photo. If none, raise Error404
    """
    vobj = user.user_validate
    photo_to_return = UserValidatePhoto.objects.filter(t_photo=t_photo, inuse=True, vid=vobj)

    if photo_to_return.exists():
        return photo_to_return[0].v_photo.path
    else:
        raise Error404("No such photo")


@default_exception(Error500)
@user_from_sid(Error404)
def submit_validate_photo(user, t_photo, photo_files_form_obj):

    def disable_former_photos(vobj):
        # Check former uploaded photos:
        formers = UserValidatePhoto.objects.filter(vid=vobj, inuse=True, t_photo=t_photo)
        for former in formers:
            former.inuse = False
            former.save()

    vobj = user.user_validate
    if vobj.validate_status != validate_status_choice.NOT_COMMITTED:
        raise Error401("Cannot change photo because already submitted the validation")

    photo = UserValidatePhoto()
    photo.t_photo = t_photo
    photo.vid = vobj
    form = ValidatePhotoUploadForm(files=photo_files_form_obj, instance=photo)
    if form.is_valid():
        disable_former_photos(vobj)
        form.save()
    else:
        raise Error403(str(form.errors))


@default_exception(Error500)
@user_from_sid(Error404)
def delete_validate_photo(user, t_photo):
    vobj = user.user_validate  # what's user_validate?
    if vobj.validate_status != validate_status_choice.NOT_COMMITTED:
        raise Error401("Cannot change photo because already submitted the validation")

    photo_to_del = UserValidatePhoto.objects.filter(t_photo=t_photo, inuse=True, vid=vobj)
    for p in photo_to_del:
        p.inuse = False
        p.save()


@default_exception(Error500)
@user_from_sid(Error404)
def save_validate(user, validate_obj=None, validate_areas=None, validate_request=0):

    def append_areas(uv, areas):
        # Delete old areas first
        va_to_delete = UserValidateArea.objects.filter(vid=uv)
        va_to_delete.delete()

        # append new areas
        for uva in areas:
            # TODO: Duplicate detection shall be implemented.
            uva["vid"] = uv.id
            uvas = UserValidateAreaSerializer(data=uva)
            if uvas.is_valid():
                uvas.save()
            else:
                if settings.DEBUG:
                    print(uvas.errors)

    # Get validation object in database, if none, create one.
    try:
        uvobj = user.user_validate
    except UserValidate.DoesNotExist:
        uvobj = UserValidate.objects.create(uid=user, validate_status=validate_status_choice.NOT_COMMITTED)

    # Cannot revert by user
    if uvobj.validate_status != validate_status_choice.NOT_COMMITTED:
        raise Error401("Already committed, cannot change")

    if validate_areas is not None:
        append_areas(uvobj, validate_areas)

    if validate_obj is None:
        validate_obj = {}

    if "validate_status" in validate_obj:
        # ignore this param
        del validate_obj["validate_status"]

    if validate_request == 0:
        validate_obj["validate_status"] = validate_status_choice.NOT_COMMITTED

    seri_before_commit = UserValidateUserSerializer(instance=uvobj, data=validate_obj, partial=True)

    # First check
    try:
        seri_before_commit.is_valid(raise_exception=True)
    except ValidationError:
        exc = seri_before_commit.errors.items()[0][1][0]
        raise WLException(code=exc.code, message=str(exc))

    if validate_request != 0:
        seri_after_commit = UserValidateUserSerializer(
            uvobj,
            data=dict(validate_obj, **{"validate_status": validate_status_choice.NOT_PROCEEDED})
        )
        try:
            seri_after_commit.is_valid(raise_exception=True)
        except ValidationError:
            seri_before_commit.save()
            exc = seri_after_commit.errors.items()[0][1][0]
            to_raise = WLException(
                code=exc.code,
                message=str(exc)
            )
            raise to_raise
        else:
            seri_after_commit.save()
    else:
        seri_before_commit.save()


@default_exception(Error500)
@user_from_sid(Error404)
def get_validate(user):
    """
    return the validate object.
    If no validate object, create one.
    :param user: user object
    :return: the validate area and photo queryset objects
    """
    try:
        validate = user.user_validate
    except UserValidate.DoesNotExist:
        validate = UserValidate.objects.create(uid=user, validate_status=validate_status_choice.NOT_COMMITTED)

    areas = validate.validate_area
    photos = validate.validate_photo.filter(inuse=True)

    return validate, areas, photos
