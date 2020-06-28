from .repoinfo import RepoInfo

def setup(bot):
    bot.add_cog(RepoInfo(bot))
    pass
