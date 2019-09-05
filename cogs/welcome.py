import discord
import logging

from discord.ext import commands


from cogs.mixins import AceMixin
from utils.checks import is_mod_pred
from utils.string_helpers import craft_welcome
from utils.configtable import ConfigTable


class Welcome(AceMixin, commands.Cog):
	'''Show welcome messages to new members.

	Welcome message replacements:
	`{user}` - member mention
	`{guild}` - server name
	`{member_count}` - server member count
	'''

	def __init__(self, bot):
		super().__init__(bot)

		self.config = ConfigTable(bot, 'welcome', 'guild_id')

	async def cog_check(self, ctx):
		return await is_mod_pred(ctx)

	@commands.Cog.listener()
	async def on_member_join(self, member):
		entry = await self.config.get_entry(member.guild.id, construct=False)

		if entry is None or entry.enabled is False or entry.content is None or entry.channel_id is None:
			return

		channel = member.guild.get_channel(entry.channel_id)

		if channel is not None:
			await channel.send(craft_welcome(member, entry.content))

	@commands.group(hidden=True)
	async def welcome(self, ctx):
		pass

	@welcome.command(aliases=['msg'])
	async def message(self, ctx, *, message: str):
		'''Set a new welcome message.'''

		if len(message) > 1024:
			raise commands.CommandError('Welcome message has to be shorter than 1024 characters.')

		# make sure an entry for this exists...
		entry = await self.config.get_entry(ctx.guild.id)
		await entry.update(content=message)

		await ctx.send('Welcome message updated. Do `welcome test` to test.')

	@welcome.command()
	async def channel(self, ctx, *, channel: discord.TextChannel = None):
		'''Set or view welcome message channel.'''

		entry = await self.config.get_entry(ctx.guild.id)

		if channel is None:
			if entry.channel_id is None:
				raise commands.CommandError('Welcome channel not yet set.')

			channel = ctx.guild.get_channel(entry.channel_id)
			if channel is None:
				raise commands.CommandError('Channel previously set but not found, try setting a new one.')

		else:
			await entry.update(channel_id=channel.id)

		await ctx.send(f'Welcome channel set to {channel.mention}')

	@welcome.command()
	async def test(self, ctx):
		'''Test your welcome command.'''

		entry = await self.config.get_entry(ctx.guild.id)

		if entry.channel_id is not None:
			channel = ctx.guild.get_channel(entry.channel_id)
		else:
			channel = False

		if entry.enabled is False:
			await ctx.send('Welcome message are disabled. Enable with `welcome enable`.')
		elif entry.content is None:
			await ctx.send('No welcome message set. Set with `welcome message <message>`')
		elif channel is None:
			await ctx.send('Welcome channel set but not found. Set a new one with `welcome channel <channel>`')
		elif channel is False:
			await ctx.send('No welcome channel set. Set with `welcome channel <channel>`')
		else:
			await self.on_member_join(ctx.author)

	@welcome.command()
	async def enable(self, ctx):
		'''Enable welcome messages.'''

		entry = await self.config.get_entry(ctx.guild.id)

		if entry.enabled is True:
			raise commands.CommandError('Welcome messages already enabled.')

		await entry.update(enabled=True)
		await ctx.send('Welcome messages enabled.')

	@welcome.command()
	async def disable(self, ctx):
		'''Disable welcome messages.'''

		entry = await self.config.get_entry(ctx.guild.id)

		if entry.enabled is False:
			raise commands.CommandError('Welcome messages already disabled.')

		await entry.update(enabled=False)
		await ctx.send('Welcome messages disabled.')


def setup(bot):
	bot.add_cog(Welcome(bot))
