from pyfcm import FCMNotification
import firebase_admin
from firebase_admin import credentials, messaging

# def send_noti(registration_ids, message_title,message_body):
#         fcm_api_key = 'JB3gUzBhIWnoDueen6stc6WzXOuXeEzUW8ikFVptxt8'
#         if fcm_api_key:
#             push_service = FCMNotification(api_key=fcm_api_key)
           
#             result = push_service.notify_multiple_devices(registration_ids=registration_ids,
#                                                           message_title=message_title,message_body=message_body)
            
# send_noti(registration_ids=[''], message_title="Hohohoho", 
#                        message_body="Heheheheheheheh.")


push_service = FCMNotification(api_key='AAAAJvI6b38:APA91bGXQ2PhgSLbrkAmZMWezV1PHUK5vA2djKSmciuKM07NpkhkmQhR3kfb9u00HlWDrIjkWAXVFdhoh7LgY2vF4qNIWcz4UrjJeOBmV0m5TKw2VX7elQb38BtS7qtdQzOxDfEjhzLv')
push_service.notify_multiple_devices(
    registration_ids=['f4TCHsLoSCSYkEDtlGvGBb:APA91bEXLoPA0Ykszfd8B3ZmcwazmYQNgLzoR7amRyqDXF7Cemz2wWFuJHeh40lNf-nGdwjF_NS-lWWfQNPRR-4B86CibT-U4BXv4qZvGAvsFqgss1OVIQhGGQHd9D56fiCc-MvLKqev',
                      'f4TCHsLoSCSYkEDtlGvGBb:APA91bEXLoPA0Ykszfd8B3ZmcwazmYQNgLzoR7amRyqDXF7Cemz2wWFuJHeh40lNf-nGdwjF_NS-lWWfQNPRR-4B86CibT-U4BXv4qZvGAvsFqgss1OVIQhGGQHd9D56fiCc-MvLKqev'],
    message_title='M-Digital HRMS',
    message_body='အွန်လိုင်းဂိမ်းဝါသနာပါတဲ့လူကြီးမင်းများအတွက်ယုံကြည်ရတဲ့ဂိမ်းဆိုဒ်လေးလမ်းညွှန်ပေးချင်ပါတယ်ရှင်❤️❤️')


 

