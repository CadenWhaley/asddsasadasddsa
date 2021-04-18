import inspect
import io
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path

import discord
import psutil
import pygit2
from discord.ext import commands

from cogs.mixins import AceMixin
from utils.converters import MaybeMemberConverter
from utils.string import yesno
from utils.time import pretty_datetime, pretty_timedelta

GITHUB_LINK = 'https://github.com/Run1e/AceBot'
GITHUB_BRANCH = 'master'

MEDALS = (
	'\N{FIRST PLACE MEDAL}',
	'\N{SECOND PLACE MEDAL}',
	'\N{THIRD PLACE MEDAL}',
	'\N{SPORTS MEDAL}',
	'\N{SPORTS MEDAL}'
)


class Meta(AceMixin, commands.Cog):
	'''Commands about the bot itself.'''

	def __init__(self, bot):
		super().__init__(bot)

		self.process = psutil.Process()

		# no blockerino so we do this here in init
		self.process.cpu_percent()

	@commands.command(aliases=['join'])
	async def invite(self, ctx):
		'''Get bot invite link.'''

		await ctx.send(self.bot.invite_link)

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def stats(self, ctx, member: MaybeMemberConverter = None):
		'''Show bot or user command stats.'''

		if member is None:
			await self._stats_guild(ctx)
		else:
			await self._stats_member(ctx, member)

	async def _stats_member(self, ctx, member):
		past_day = datetime.utcnow() - timedelta(days=1)

		first_command = await self.db.fetchval(
			'SELECT timestamp FROM log WHERE guild_id=$1 AND user_id=$2 LIMIT 1',
			ctx.guild.id, member.id
		)

		total_uses = await self.db.fetchval(
			'SELECT COUNT(id) FROM log WHERE guild_id=$1 AND user_id=$2',
			ctx.guild.id, member.id
		)

		commands_alltime = await self.db.fetch(
			'SELECT COUNT(id), command FROM log WHERE guild_id=$1 AND user_id=$2 GROUP BY command '
			'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, member.id
		)

		commands_today = await self.db.fetch(
			'SELECT COUNT(id), command FROM log WHERE guild_id=$1 AND user_id=$2 AND timestamp > $3 '
			'GROUP BY command ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, member.id, past_day
		)

		e = discord.Embed()
		e.set_author(name=member.name, icon_url=member.avatar_url)
		e.add_field(name='Top Commands', value=self._stats_craft_list(commands_alltime))
		e.add_field(name='Top Commands Today', value=self._stats_craft_list(commands_today))

		self._stats_embed_fill(e, total_uses, first_command)

		await ctx.send(embed=e)

	async def _stats_guild(self, ctx):
		past_day = datetime.utcnow() - timedelta(days=1)
		total_uses = await self.db.fetchval('SELECT COUNT(id) FROM log WHERE guild_id=$1', ctx.guild.id)

		first_command = await self.db.fetchval(
			'SELECT timestamp FROM log WHERE guild_id=$1 LIMIT 1', ctx.guild.id
		)

		commands_today = await self.db.fetch(
			'SELECT COUNT(id), command FROM log WHERE guild_id=$1 AND timestamp > $2 GROUP BY command '
			'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, past_day
		)

		commands_alltime = await self.db.fetch(
			'SELECT COUNT(id), command FROM log WHERE guild_id=$1 GROUP BY command ORDER BY COUNT DESC LIMIT 5',
			ctx.guild.id
		)

		users_today = await self.db.fetch(
			'SELECT COUNT(id), user_id FROM log WHERE guild_id=$1 AND timestamp > $2 GROUP BY user_id '
			'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, past_day
		)

		users_alltime = await self.db.fetch(
			'SELECT COUNT(id), user_id FROM log WHERE guild_id=$1 GROUP BY user_id '
			'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id
		)

		e = discord.Embed()
		e.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
		e.add_field(name='Top Commands', value=self._stats_craft_list(commands_alltime))
		e.add_field(name='Top Commands Today', value=self._stats_craft_list(commands_today))

		e.add_field(
			name='Top Users',
			value=self._stats_craft_list(users_alltime, [f'<@{user_id}>' for _, user_id in users_alltime])
		)

		e.add_field(
			name='Top Users Today',
			value=self._stats_craft_list(users_today, [f'<@{user_id}>' for _, user_id in users_today])
		)

		self._stats_embed_fill(e, total_uses, first_command)

		await ctx.send(embed=e)

	def _stats_embed_fill(self, e, total_uses, first_command):
		e.description = f'{total_uses} total commands issued.'
		if first_command is not None:
			e.timestamp = first_command
			e.set_footer(text='First command invoked')

	def _stats_craft_list(self, cmds, members=None):
		value = ''
		for index, cmd in enumerate(cmds):
			value += f'\n{MEDALS[index]} {members[index] if members else cmd[1]} ({cmd[0]} uses)'

		if not len(value):
			return 'None so far!'

		return value[1:]

	def format_commit(self, commit):
		short, _, _ = commit.message.partition('\n')
		short_sha2 = commit.hex[0:6]
		tz = timezone(timedelta(minutes=commit.commit_time_offset))
		time = datetime.fromtimestamp(commit.commit_time).replace(tzinfo=tz)
		offset = pretty_datetime(time.astimezone(timezone.utc).replace(tzinfo=None), ignore_time=True)
		return f'[`{short_sha2}`]({GITHUB_LINK}/commit/{commit.hex}) {short} ({offset})'

	def get_last_commits(self, count=3):
		repo = pygit2.Repository('.git')
		return '\n'.join(self.format_commit(c) for c in islice(repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL), count))

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def about(self, ctx, *, command: str = None):
		'''Show info about the bot or a command.'''

		if command is None:
			await self._about_bot(ctx)
		else:
			cmd = self.bot.get_command(command)
			if cmd is None or cmd.hidden:
				raise commands.CommandError('No command with that name found.')
			await self._about_command(ctx, cmd)

	async def _about_bot(self, ctx):
		e = discord.Embed(title='Official bot invite link here!', description=self.get_last_commits(), url=self.bot.invite_link)

		owner = self.bot.get_user(self.bot.owner_id)
		e.set_author(name=str(owner), icon_url=owner.avatar_url)

		e.add_field(name='Developer', value=str(self.bot.get_user(self.bot.owner_id)))

		invokes = await self.db.fetchval('SELECT COUNT(*) FROM log')
		e.add_field(name='Command invokes', value='{0:,d}'.format(invokes))

		guilds, text, voice, users = 0, 0, 0, 0

		for guild in self.bot.guilds:
			guilds += 1
			users += len(guild.members)
			for channel in guild.channels:
				if isinstance(channel, discord.TextChannel):
					text += 1
				elif isinstance(channel, discord.VoiceChannel):
					voice += 1

		unique = len(self.bot.users)

		e.add_field(name='Servers', value=str(guilds))

		memory_usage = self.process.memory_full_info().uss / 1024 ** 2
		cpu_usage = self.process.cpu_percent() / psutil.cpu_count()

		e.add_field(name='Process', value='CPU: {0:.2f}%\nMemory: {1:.2f} MiB'.format(cpu_usage, memory_usage))

		e.add_field(name='Members', value='{0:,d} total\n{1:,d} unique'.format(users, unique))
		e.add_field(name='Channels', value='{0:,d} total\n{1:,d} text channels\n{2:,d} voice channels'.format(text + voice, text, voice))

		now = datetime.utcnow()
		e.set_footer(text='Last restart {0} ago'.format(pretty_timedelta(now - self.bot.startup_time)))

		await ctx.send(embed=e)

	async def _about_command(self, ctx, command: commands.Command):
		e = discord.Embed(title=command.qualified_name + ' ' + command.signature, description=command.description or command.help)

		e.add_field(name='Qualified name', value=command.qualified_name)

		try:
			can_run = await command.can_run(ctx)
		except commands.CommandError:
			can_run = False

		e.add_field(name='Can you run it?', value=yesno(can_run))

		e.add_field(name='Enabled', value=yesno(command.enabled))

		invokes = await self.db.fetchval('SELECT COUNT(*) FROM log WHERE command=$1', command.qualified_name)
		e.add_field(name='Total invokes', value='{0:,d}'.format(invokes))

		here_invokes = await self.db.fetchval('SELECT COUNT(*) FROM log WHERE command=$1 AND guild_id=$2', command.qualified_name, ctx.guild.id)
		e.add_field(name='Invokes in this server', value='{0:,d}'.format(here_invokes))

		if command.aliases:
			e.set_footer(text='Also known as: ' + ', '.join(command.aliases))

		await ctx.send(embed=e)

	@commands.command(aliases=['fb'])
	@commands.cooldown(rate=2, per=120.0, type=commands.BucketType.user)
	async def feedback(self, ctx, *, feedback: str):
		'''Give me some feedback about the bot!'''

		with open('feedback/{}.feedback'.format(str(ctx.message.id)), 'w', encoding='utf-8-sig') as f:
			f.write(ctx.stamp + '\n\n' + feedback)

		await ctx.send('Feedback sent. Thanks for helping improve the bot!')

	@commands.command()
	async def support(self, ctx):
		'''Get link to support server.'''

		await ctx.send(self.bot.support_link)

	@commands.command(name="code", aliases=["src", "source"])
	async def source(self, ctx: commands.Context, source_item: str = None):
		"""Get a github link to the source code of a command."""

		if source_item is None:
			await ctx.send(GITHUB_LINK)
			return

		# send a typing event 
		# normally would be an async with,
		# but no need to do so since it shouldn't take very long to do this code,
		await ctx.trigger_typing()

		cmd: commands.Command = self.bot.get_command(source_item)

		if cmd is None:
			raise commands.CommandError("Couldn't find command.")
		callback = cmd.callback
		source_file = str(
			Path(inspect.getsourcefile(callback)).relative_to(str(Path.cwd()))
		)

		# get repo to check if its an ignored file
		repo = pygit2.Repository('.git')

		if pygit2.GIT_STATUS_IGNORED & repo.status_file(source_file):
			# hide all commands in all git ignored files
			raise commands.CommandError("Couldn't find command.")

		lines, first_line_no = inspect.getsourcelines(callback)

		lines_extension = f"#L{first_line_no}-L{first_line_no+len(lines)-1}"
		link = f"{GITHUB_LINK}/blob/{GITHUB_BRANCH}/{source_file}{lines_extension}"

		# check for image permissions and if we don't have them then just send the link
		if not ctx.channel.permissions_for(ctx.me) >= discord.Permissions(embed_links=True):
			await ctx.send(link)
			return

		# make a fancy embed!
		embed = discord.Embed(title=cmd.qualified_name,
		                      description=f'[Open in Github]({link} "Github Repository Link")',)
		embed.set_footer(
			text=f"/{source_file}", icon_url='https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png')
		await ctx.send(embed=embed)


def setup(bot):
	bot.add_cog(Meta(bot))
