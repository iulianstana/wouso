from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils import simplejson
from models import *


from wouso.core.config.models import BoolSetting
from datetime import datetime, timedelta
#import datetime


def create_room(roomName, deletable=False, renameable=False):
    ''' creates a new chatroom and saves it '''
    newRoom = ChatRoom(name=roomName, deletable=deletable, renameable=renameable)
    newRoom.save()
    return newRoom

def get_author(request):

    return request.user.get_profile().get_extension(ChatUser)


def add_message(text, sender, toRoom):

    timeStamp = datetime.now()

    diff = timeStamp - sender.lastMessageTS

    #TODO: Putem renunta la spam:) este inutil.
    difference_in_seconds = 1;
    #difference_in_seconds = (diff.microseconds + (diff.seconds + diff.days * 24 * 3600) * 10**6) / 10**6
    #if diff.total_seconds() > 0.5:
    if difference_in_seconds > 0.5:
        msg = ChatMessage(content=text, author=sender, destRoom=toRoom, timeStamp=timeStamp)
        msg.save()
    else:
        raise ValueError('Spam')


def serve_message(user, room=None, position=None):


    obj = {'user': unicode(user)}
    if(room == None):
        query = ChatMessage.objects.filter(timeStamp__gt=user.lastMessageTS, destRoom__participants=user)
        obj['count'] = query.count()
    else:
        number = int(position)
        query = ChatMessage.objects.filter(destRoom=room)
        query = query[len(query)-number-10:] if len(query) > (10 + number) else query

        number_query = 10 if len(query) == 0 else len(query) - number
        obj['count'] = number_query


    if not query:
        return None

    msgs = []
    for m in query:
        mesaj = {}
        mesaj['room'] = m.destRoom.name
        mesaj['user'] = unicode(m.author)
        mesaj['text'] = m.content
        lastTS = m.timeStamp
        msgs.append(mesaj)
    if(room == None):
        user.lastMessageTS = lastTS
        user.save()

    obj['msgs'] = msgs

    return obj


@login_required
def index(request):
    if BoolSetting.get('disable-Chat').get_value():
        return HttpResponseRedirect(reverse('wouso.interface.views.homepage'))

    oldest = datetime.now() - timedelta(minutes = 10)
    online_last10 = Player.objects.filter(last_seen__gte=oldest).order_by('-last_seen')

    user = request.user.get_profile()
    return render_to_response('chat/chat.html',
                            {'user': user,
                             'last': online_last10,
                            },
                            context_instance=RequestContext(request))


@login_required
def log_request(request):

    Room = roomexist('global')

    all_message = ChatMessage.objects.filter(destRoom=Room)
    all_message = all_message[len(all_message)-50:] if len(all_message) > 50 else all_message

    return render_to_response('chat/global_log.html',
                            {
                            'log':all_message,
                            },
                            context_instance=RequestContext(request))


@login_required
def online_players(request):

    # gather users online in the last ten minutes
    oldest = datetime.now() - timedelta(hours = 1000)
    online_last10 = Player.objects.filter(last_seen__gte=oldest).order_by('user__username')

    return render_to_response('chat/chat_last.html',
                            {
                            'last': online_last10,
                            },
                            context_instance=RequestContext(request))



@login_required
def private_log(request):

    user = get_author(request)
    position = request.POST['number']

    room = roomexist(request.POST['room'])
    return HttpResponse(simplejson.dumps(serve_message(user, room, position)))


@login_required
def sendmessage(request):
    """ Default endpoint (/chat/m/)
    """
    user = get_author(request)
    data = request.REQUEST

    if data['opcode'] == 'message':
        room = roomexist(data['room'])
        try:
            assert room is not None
            add_message(data['msg'], user, room)
        except (ValueError, AssertionError):
            return HttpResponseBadRequest()
    elif data['opcode'] == 'keepAlive':
        chat_global = roomexist('global')
        if user not in chat_global.participants.all():
            chat_global.participants.add(user)
    elif data['opcode'] == 'getRoom':
        try:
            user_to = Player.objects.get(id=data['to'])
            user_to = user_to.get_extension(ChatUser)
        except ChatUser.DoesNotExist:
            return HttpResponseBadRequest()
        rooms = ChatRoom.objects.exclude(name='global').filter(participants=user).filter(participants=user_to)
        rooms = [r for r in rooms if r.participants.count() <= 2]
        if len(rooms) > 1:
            return HttpResponseBadRequest()
        if rooms:
            room = rooms[0]
        else:
            name = '%d-%d' % ((user.id, user_to.id) if user.id < user_to.id else (user_to.id, user.id))
            room = create_room(name)
        room.participants.add(user)
        room.participants.add(user_to.id)
        return json_response(room.to_dict())
    return HttpResponse(simplejson.dumps(serve_message(user, None, None)))

def json_response(object):
     return HttpResponse(simplejson.dumps(object))

def roomexist(room_name):
    try:
        return ChatRoom.objects.get(name = room_name)
    except ChatRoom.DoesNotExist:
        return None

