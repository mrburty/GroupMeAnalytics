import requests
import sys
from pprint import pprint
import argparse
import csv


def get_groups():
    response = requests.get('https://api.groupme.com/v3/groups?token=' + TOKEN)
    return response.json()['response']


def log_groups(groups):
    if len(groups) == 0:
        print('You are not part of any groups.')
        return
    for i, group in enumerate(groups):
        print('%d. %s' % (i, group['name']))


def new_user(name):
    return {'name': name, 'messages_sent': 0, 'likes_given': 0, 'likes_received': 0, 'words_sent': 0, 'likes_by_member': {}, 'shared_likes': {}, 'self_likes': 0}


def prepare_user_dictionary(members):
    return {member['user_id']: new_user(member['name']) for member in members}


def analyze_group(group, users, message_count):
    message_id = 0
    message_number = 0
    while message_number < message_count:
        params = {
            # Get maximum number of messages at a time
            'limit': 100,
        }
        if message_id:
            params['before_id'] = message_id
        response = requests.get('https://api.groupme.com/v3/groups/%s/messages?token=%s' % (group['id'], TOKEN), params=params)
        messages = response.json()['response']['messages']
        for message in messages:
            message_number += 1

            name = message['name']
            text = message['text'] or ''

            # Word count
            for char in '-.,\n':
                text = text.replace(char, ' ')
            message_word_count = len(text.split())

            sender_id = message['sender_id']
            likers = message['favorited_by']

            if sender_id not in users.keys():
                users[sender_id] = new_user(name)

            # Fill in name if it's not in the dictionary
            if not users[sender_id]['name']:
                users[sender_id]['name'] = name

            for user_id in likers:
                if users[sender_id]['likes_by_member'].get(user_id):
                    users[sender_id]['likes_by_member'][user_id] += 1
                else:
                    users[sender_id]['likes_by_member'][user_id] = 1

            # Count shared likes
            for user_id in likers:
                if user_id not in users.keys():
                    # Leave name blank for now
                    users[user_id] = new_user('')
                if sender_id == user_id:
                    users[sender_id]['self_likes'] += 1
                    continue  # pass because you don't want to count yourself as sharing likes with yourself
                for user_id_inner in likers:
                    if users[user_id]['shared_likes'].get(user_id_inner):
                        users[user_id]['shared_likes'][user_id_inner] += 1
                    else:
                        users[user_id]['shared_likes'][user_id_inner] = 1
                users[user_id]['likes_given'] += 1
            users[sender_id]['messages_sent'] += 1  # add one to sent message count
            users[sender_id]['likes_received'] += len(likers)
            users[sender_id]['words_sent'] += message_word_count

        message_id = messages[-1]['id']  # Get last message's ID for next request
        remaining = 100 * message_number / message_count
        print('\r%.2f%% done' % remaining, end='')
    print()
    return users


def display_data(users):
    for key in users:
        try:
            likes_per_message = users[key]['likes_received'] / users[key]['messages_sent']
        except ZeroDivisionError:
            likes_per_message = 0
        print(('{name} | Messages sent: {messages}, Likes given: {likes}, Self-likes: {self_likes}, Likes received: {likes_received}, ' +
            'Avg. Likes per message: {likes_per_message:.2f}, Words sent: {words_sent}'
                ).format(name=users[key]['name'],
                        messages=users[key]['messages_sent'],
                        likes=users[key]['likes_given'],
                        self_likes=users[key]['self_likes'],
                        likes_received=users[key]['likes_received'],
                        likes_per_message=likes_per_message,
                        words_sent=users[key]['words_sent']))

        """
        print('Portion of total likes received by member:', end=' ')
        for key_inner in users[key]['likes_by_member']:
            try:
                percent = (users[key]['likes_by_member'][key_inner] / users[key]['likes_given']) * 100
            except ZeroDivisionError:
                percent = 0
            print('{name}: {percent}'.format(name=users[key_inner]['name'], percent=percent), end=' ')
        print()

        print('Like sharing rates:', end=' ')
        for key_inner in users[key]['shared_likes']:
            try:
                percent = (users[key]['shared_likes'][key_inner] / users[key]['likes_received']) * 100
            except ZeroDivisionError:
                percent = 0
            print('{name}: {percent}'.format(name=users[key_inner]['name'], percent=percent), end=' ')
        print()
        print()
        """

def save(users):
    """
    Save user data to CSV file.
    """
    with open('users.csv', 'w+') as f:
        writer = csv.writer(f)
        columns = ['name', 'messages_sent', 'likes_given', 'self_likes', 'likes_received', 'words_sent']
        writer.writerow(columns)
        for key in users:
            writer.writerow([users[key][column] for column in columns])

parser = argparse.ArgumentParser(description='Analyze a GroupMe chat')
parser.add_argument('token', help='Your GroupMe developer token')
args = parser.parse_args()

TOKEN = args.token
if not TOKEN:
    from getpass import getpass
    print('If you have not done so already, go to the following website to receive your API token: ' +
          'https://dev.groupme.com/. When signing up, it does not matter what you put for the callback URL. ' +
          'Alternately, click "Access Token" to use your account for authentication.')
    TOKEN = getpass('Enter your developer access token (hidden): ')

groups = get_groups()
log_groups(groups)

try:
    group_number = int(input('Enter the number of the group you would like to analyze: '))
except ValueError:
    print('Not a number')

group = groups[group_number]

# Display basic group data before analysis
group_name = group['name']
message_count = group['messages']['count']
print('Analyzing %d messages from %s' % (message_count, group_name))

# Put all the members currently in group into a dict
members = group['members']
users = prepare_user_dictionary(members)

# Iterate through messages to collect data
users = analyze_group(group, users, message_count)

# Show data
display_data(users)
save(users)
