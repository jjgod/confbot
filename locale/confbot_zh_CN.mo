��    J      l  e   �      P     Q     Z  /   h     �  	   �  
   �     �     �  K   �  /   3     c     x     �     �  
   �  �   �     g     ~  
   �     �     �     �     �  m   �     U	     e	     ~	     �	      �	     �	  
   �	  ,   �	     	
     
     $
  �   1
  
   �
     �
      �
  4   �
           =     L     b  &        �  x   �  "   8     [  �   r  �   	  �   �  �   &  %   �  !   �  )     	   I     S     m     |  #   �  &   �     �     �     �     �     �     �                    %     +  �  2     �  
   �     �     �       
   *      5     V  Q   k  &   �     �     �  &        A     _    t     �      �     �     �     �     �       �  6     #     ?     [     j  '   �     �     �  0   �                '  �   <     (     5     <  *   [     �     �     �     �  )   �     #     B  !   �     �  �   �  �   �  �   �  �   /     �     	  '     	   D     N     j  !   �  &   �  '   �     �  	            	               #      0   	   7      A   	   W      a      F      :                        I   7   C       ?   >          D       8              J       &                             6   <           #   -       (   G   !   0           ;   .      '                 $   H           5      	            3      %   
         )   "          B          *      A   4   ,             +             E   9   /          1      2   @      =    %s is %s %s is %s (%s) %s is being a moron trying to flood the channel %s is not banned *<%s>* %s <%s> %s %s <%s> added you as an admin <%s> has left <%s> has set himself in "nochat" mode, so you could not send him a message. <%s> is a super admin which can not be deleted. <%s> is not an admin <%s> joins this room. <%s> removed you as an admin >%s> %s Added <%s> Admin commands: ")die" ")addadmin" ")deladmin" ")listadmins" ")kick" ")listbans" ")ban" ")unban" ")invite" ")reload" ")addemote" ")delemote" ")listoptions" ")setoption" Admin shutdown by <%s> Admin shutdown by <%s> (%s) Admins: %s Available languages: %s Banned list: %s Banned: <%s> Booted: <%s> Commands: ")help" "/me" ")names" ")quit" ")msg" ")nochat" ")chat" ")status" ")listemotes" ")lang" ")listlang" Config reloaded Emote [%s] is not exist. Emotes : 
%s Feature not implemented Input super admin email account: Invited <%s> Names: 
%s Option [%s] may not exist or can not be set. Options: 
%s Quit: <%s> %s Removed <%s> See http://coders.meta.net.nz/~perry/jabber/confbot.php for more details.
Also see http://www.donews.net/limodou for Chinese version. Status: %s Success This is a private conference bot This is admin command, you have no permision to use. Topic: %(topic)s
%(lastlog)s Unbanned: <%s> Unknown command "%s". Usage: )msg <nick> <message> Usage: /addemote action representation Usage: /delemote <emote> Usage: /me <emote>
Says an emote as you.  eg "/me %(action)s <msg>" shows as "%(nick)s %(emote)s <msg>" to everyone else Usage: /setoption <option> <value> User %s is not exists. Version: %s (%s)
See http://coders.meta.net.nz/~perry/jabber/confbot.php for more details.
Also see http://www.donews.net/limodou for Chinese version. Warning: Because you set "nochat" flag, so you can not receive and send any message from this bot, until you reset using "/chat" command Warning: You are marked as "busy" in your client,
you will not see other people talk,
set yourself "available" in your client to see their replies. Welcome to ConferenceBot %(version)s
By Isomer (Perry Lorier) and Limodou
This conference bot is set up to allow groups of people to chat.
)help to list commands, )quit to quit What is the account name of your bot: What is the password of your bot: Write a short description about your bot: You %s %s You are an admin already. You are banned You can begin to chat now. Your language has been set as "%s". Your language has been set as default. away claps cries farts here hops joining jumps keels over and dies sighs smiles Project-Id-Version: confbot 1.5b
POT-Creation-Date: Tue Sep 06 11:05:19 2005
PO-Revision-Date: 2005-09-08 17:32+0800
Last-Translator: limodou <limodou@gmail.com>
Language-Team: confbot <limodou@gmail.com>
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit
Generated-By: pygettext.py 1.5
X-Poedit-Language: Chinese
X-Poedit-Country: CHINA
X-Poedit-SourceCharset: utf-8
 %s %s %s %s (%s) %s 正在对聊天频道刷屏 %s 没有被禁止 <%s> _对你悄悄说_ ：%s <%s> %s %s <%s> 已经把你加为管理员 <%s> 已经离开了 <%s> 已经把自已设置为 "nochat" 模式，所以你不能给他发信息。 <%s> 是超级管理员不能被删除 <%s> 不是一个管理员 <%s> 加入本聊天室。 <%s> 已经取消你的管理员资格 你对 <%s> _悄悄说_ ：%s <%s> 已经被加入 管理员命令列表: 
/die             关闭聊天频道
/addadmin <nick> 增加管理员
/deladmin <nick> 删除管理员
/listadmins      列出管理员列表
/kick <nick>     踢除某个人
/ban <nick>      禁止某人人
/unban <nick>    解决对某人的禁止
/listbans        显示禁止人名单
/invite <nick>   邀请某人加入聊天
/reload          重新装入配置信息
/addemote        增加表情串
/delemote        删除表情串
/listoptions     显示选项列表
/setoption       设置选项 聊天频道被 <%s> 关闭 聊天频道被 <%s> 关闭 (%s) 管理员列表: %s 可用的语言: %s 被禁止名单: %s <%s> 已经被禁止加入了 <%s> 已经被踢出去了 命令列表：
/help        显示本帮助信息
/me <emote> <msg> 设置表情串
/names       显示聊天室人名
/quit <msg>  退出聊天室，一旦退出需要重新加入
/msg <nick> <msg>  私聊
/nochat      置为非聊天状态，不接收和发送任何信息
/chat        置为聊天状态
/status <nick>  查看状态，管理员可以查看某人状态
/listemotes  显示所有表情串
/lang <lang> 语言设置，无参数为清除
/listlang    显示可用语言列表 配置信息已经被刷新 表情串 [%s] 不存在。 表情串: 
%s 此特性尚未实现 请输入超级管理员邮件帐户： <%s> 已经被邀请 聊天名单: 
%s 选项 [%s] 可能不存在或不能被设置。 选项列表: 
%s <%s> 已经退出 %s <%s> 已经被删除 查看 http://coders.meta.net.nz/~perry/jabber/confbot.php 以了解更多的细节。
查看 http://www.donews.net/limodou 了解关于汉化版的细节。
查看 http://wiki.woodpecker.org.cn/moin/GoogleTalkBot 了解更多体验。 状态： %s 成功 这是一个私人聊天频道 这是管理员命令，你无权使用。 主题: %(topic)s
%(lastlog)s <%s> 已经被取消禁止了 未知的命令 "%s"。 用法：/msg <nick> <message> 用法：/addemote 单词名 表情涵义 用法：/delemoet <表情串> 用法: /me <表情串> <消息>
表现你的一种表情。如：/me %(action)s <msg>
将表示为 %(nick)s %(emote)s <消息> 用法：/setoption 选项名 值 用户 %s 不存在。 版本: %s (%s)
查看 http://coders.meta.net.nz/~perry/jabber/confbot.php 以了解更多的细节。
查看 http://www.donews.net/limodou 了解关于汉化版的细节。
查看 http://wiki.woodpecker.org.cn/moin/GoogleTalkBot 了解更多体验。 警告：因为你设置了 "nochat" 标志，所以你不能从本机器人接收和发送任何消息，直到你使用"/chat"命令重设 警告: 你已经在客户端标记为"忙(busy)",
你将不会收到其他人的谈话，在客户端将你自已
设为"在线(available)"才可以看到别人的回复 欢迎加入Conferencebot %(version)s
由Isomer(Perry Lorier)和Limodou编写
本会议机器人是为了允许多人聊天而建立的。

/help 可以查看命令列表 /quit 退出聊天频道 你的Bot帐户名： 你的Bot口令： 写下关于你的Bot的简短描述： 你 %s %s 你已经是管理员了。 你被禁止加入聊天频道 你现在可以开始聊天了。 你的语言已经被设置为 "%s"。 你的语言已经被设置为缺省。 不在 拍着手 哭着 放着屁 在线 单脚跳着 加入 跳起来 翻倒在地死掉了 唉着气 微笑 